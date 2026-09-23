# Multi-Agent Harness Benchmark: INT-822 Evidence Bundle Caching

**Date:** September 23, 2026  
**Target Repository:** [`wearebeam/interpret-investigator-agent`](https://github.com/wearebeam/interpret-investigator-agent)  
**Ticket:** [INT-822](https://linear.app/beam/issue/INT-822) — *Shared evidence bundle caching for Interpret investigator agent*  
**Harnesses Evaluated:** Cursor Desktop, Claude Code (CLI), OpenCode, Codex CLI  
**Workflow Engine:** `joel-workflow` (migrated v2.20.2 → v2.20.3 → v2.20.4)

---

## 1. Executive Summary

This benchmark evaluated four distinct agent harness configurations on an identical distributed systems task: refactoring the incident investigator agent to eliminate redundant multi-megabyte evidence fetches by introducing a shared filesystem cache, a loopback MCP server for capped/recorded refreshes, and runner pre-fetch wiring.

| Metric | Cursor (Winner) | Claude Code v2 | OpenCode v2 | Codex CLI v2 |
|---|---|---|---|---|
| **Topology** | In-session coordinator/implementer + cross-model reviewer | Dual-agent coordinator + headless implementer/auditor | Headless coordinator/implementer | Single-agent CLI |
| **Coordinator** | Claude 3.5 Opus / Opus 5.5 (`opus[1m]`) | Claude Fable (`fable[1m]`) | GPT-6 Astra (`openai/gpt-6-astra`) | GPT-5.6 Sol / GPT-6 Astra |
| **Implementer** | Opus 5.5 (direct in-session) | Codex Astra (`gpt-6-astra`) | GPT-6 Astra | GPT-5.6 Sol |
| **Reviewer** | GPT-6 Luna (`gpt-6-luna`) | Codex Astra (`gpt-6-astra`) | GPT-6 Astra (self/audit) | Sol / Astra |
| **PR Output** | **3 clean PRs** ([#46](https://github.com/wearebeam/interpret-investigator-agent/pull/46), [#47](https://github.com/wearebeam/interpret-investigator-agent/pull/47), [#48](https://github.com/wearebeam/interpret-investigator-agent/pull/48)) | 5 PRs ([#41](https://github.com/wearebeam/interpret-investigator-agent/pull/41)–[#45](https://github.com/wearebeam/interpret-investigator-agent/pull/45)) | 5 PRs ([#36](https://github.com/wearebeam/interpret-investigator-agent/pull/36)–[#40](https://github.com/wearebeam/interpret-investigator-agent/pull/40)) | 3 PRs ([#33](https://github.com/wearebeam/interpret-investigator-agent/pull/33)–[#35](https://github.com/wearebeam/interpret-investigator-agent/pull/35)) |
| **Outcome** | **Merged cleanly to `main`** | Closed (scope creep) | Closed (review idle) | Closed (superseded) |
| **Total Runtime** | ~28 min | ~115 min | ~65 min | ~42 min |
| **Dominant Latency** | Direct code authoring & verify | **85m+ adversarial debate on host UID security** | **45m spent across 4 clean reviews** | Manual stack stitching & CLI polling |

**Key Finding:** Across all runs, raw code generation and unit test verification accounted for less than 20% of total elapsed time. The overwhelming latency driver was **the Adversarial Tax**—unconstrained multi-agent review loops where coordinators and auditors debated platform-level trust boundaries far outside the ticket's scope. 

The empirical findings from this benchmark led directly to the core optimizations in `joel-workflow` v2.20.3 and v2.20.4 (Architectural Observation Rule, 1-Round Plan Audit Cap, Stage-6 Consolidated Review, and Direct Execution default).

---

## 2. Test Task Specification (INT-822)

The investigator agent runs inside ephemeral execution containers. During investigation cycles, it was fetching complete Honeycomb spans, BigQuery telemetry, and Interpret traces multiple times per incident, leading to rate limits, network timeouts, and inflated run times.

### Acceptance Criteria
1. **Fetch-Once CLI & Shared Cache**: Bundle download logic extracted into a reusable CLI script and cache store in a private run directory.
2. **Capped Evidence Refresh via MCP**: Local server exposing bounded evidence refresh tools over loopback so Claude cannot trigger arbitrary unbounded remote queries.
3. **Runner Wiring**: Harness runner provisions the bundle once before the agent starts and passes the cached path directly.
4. **Verification**: Full unit tests covering caching, corrupted payloads, concurrency, and network error recovery.

---

## 3. Harness Performance & Failure Mode Analysis

### A. Cursor (Opus 5.5 Implementer + Luna Reviewer) — WINNER
- **Architecture**: In-session execution where Opus 5.5 acted as both architect and implementer, coupled with GPT-6 Luna for out-of-band cross-model review.
- **Why it won**:
  - **Zero Subagent Friction**: Bypassed JSON-RPC/file-based subagent handoffs. Opus 5.5 planned the 3-PR stack cleanly, adhering strictly to the repository conventions without over-engineering.
  - **Sharp, Non-Blocking Review**: Luna reviewed the branch diff (`base...HEAD`), highlighting genuine boundary edge cases (cache invalidation on corrupted JSON) without fabricating out-of-scope infrastructure requirements.
  - **Incremental Delivery**: Delivered 3 perfectly scoped PRs ([PR #46](https://github.com/wearebeam/interpret-investigator-agent/pull/46), [PR #47](https://github.com/wearebeam/interpret-investigator-agent/pull/47), [PR #48](https://github.com/wearebeam/interpret-investigator-agent/pull/48)) that merged into `main` with zero merge conflicts.

### B. Claude Code v2 (Fable Coordinator + Codex Astra Implementer/Reviewer)
- **Architecture**: Claude Code running Fable (`fable[1m]`) planning and driving headless Codex Astra (`gpt-6-astra`) via `e2e-codex.sh`.
- **Failure Mode — Adversarial Amplification**:
  - Astra identified that running Claude in the same container gave it read access to container environment variables.
  - Fable accepted this as a blocking defect, expanding scope into creating a dedicated OS-level user split ([PR #45](https://github.com/wearebeam/interpret-investigator-agent/pull/45): *"Run Claude as a separate user so it cannot read harness secrets"*).
  - The two agents spent **85 minutes** attempting to solve container user namespaces, Docker UID mapping, and file permission handoffs in an application caching ticket.
  - Result: 5 PRs created, high token cost, scope blew out, abandoned in favor of the clean Cursor stack.

### C. OpenCode v2 (GPT-6 Astra)
- **Architecture**: Headless OpenCode orchestrating tasks using OpenAI GPT-6 Astra.
- **Failure Mode — Redundant Review Ceremony**:
  - For each task commit, the coordinator triggered full independent audit routines.
  - 4 consecutive audit cycles returned completely clean verdicts (`READY` / no defects found), yet each cycle required full context reloading and prompt evaluation.
  - **45 minutes** were spent waiting for reviews that produced no actionable diffs or findings.

### D. Codex CLI v2 (GPT-5.6 Sol / GPT-6 Astra)
- **Architecture**: Standalone Codex CLI executing tasks linearly in isolated worktrees.
- **Performance**: High code accuracy (clean Python implementations of the cache layer), but high manual coordination overhead to slice into stacked PRs and verify dependencies.

---

## 4. Systemic Fixes Codified in `joel-workflow`

Based on the empirical evidence gathered in this benchmark, the following changes were implemented across `skills/e2e/SKILL.md`, `commands/ship.md`, and `scripts/e2e-codex.sh`:

### 1. Architectural Observation Rule (`v2.20.3`)
- **Problem**: Reviewers blocking application PRs on preexisting infrastructure, OS, or platform trust boundaries (e.g. Fable's 85m container UID excursion).
- **Rule**: Out-of-scope environmental or platform limitations not requested by the ticket must be recorded as non-blocking `Architectural Observation` items for future consideration, never as blocking `REVISE` defects.

### 2. 1-Round Plan Audit Cap (`v2.20.3`)
- **Problem**: Unbounded multi-round plan debates between coordinator and auditor.
- **Rule**: Exactly one plan audit round. The coordinator reviews findings once, disposes valid vs. invalid items, and presents both the plan and dispositions directly to the human at the approval gate.

### 3. Consolidated Stage-6 Review (`v2.20.3`)
- **Problem**: Dispatching independent reviewer subagents during active task coding tripled elapsed time for routine code.
- **Rule**: Eliminate per-task reviewer subagent dispatch during active construction. Consolidate adversarial cross-model scrutiny at Stage 6 over the complete branch diff (`base...HEAD`).

### 4. Direct Execution as Default (`v2.20.4`)
- **Problem**: Subagent execution serialization overhead (`e2e-codex.sh` IPC, JSONL parsing, prompt staging) added 3–5 minutes per task even when no errors occurred.
- **Rule**: Set `--execution direct` (in-session execution by coordinator) as default, paired with `--review codex` defaulting to `gpt-6-luna` for out-of-band cross-model verification. Added `--direct`, `--impl <model>`, and `--review <model>` CLI shorthands.

### 5. Stack Delivery & Merge Automation (`commands/ship.md`)
- **Problem**: Stacked PRs failed standard merge workflows due to GitHub's requirement for asynchronous merge endpoints (`PUT /repos/.../pulls/{n}/merge-async`) and review bots stalling on intermediate branches.
- **Rule**: Skipped the 3-minute review-bot polling pause on intermediate stack PRs; added documentation for async merge handling.

---

## 5. Playbook for Future Model & Harness Bake-Offs

When benchmarking future model generations (e.g. Claude Opus 5.5 vs GPT-6 Luna vs open models) or new harnesses:

1. **Task Selection**:
   - Use multi-PR distributed tasks requiring architectural slicing, persistence, and external protocol integration (e.g. MCP, loopback HTTP, CLI). Avoid trivial single-file puzzles.
2. **Standard Harness Prompt**:
   - Standard prompt structure: Ticket link, acceptance criteria, iron laws, and strict instruction to budget PRs at $\le 500$ lines.
3. **Execution Telemetry**:
   - Record timestamps at four distinct milestones:
     1. Planning completion & Human gate (`t_plan`)
     2. Task implementation completion (`t_impl`)
     3. Adversarial review & fix cycle (`t_review`)
     4. Ship verification & PR creation (`t_ship`)
4. **Scoring Rubric**:
   - **Signal-to-Noise Ratio (SNR)**: Number of valid defects caught vs out-of-scope / hallucinated blockers.
   - **Wall-Clock Latency**: Time to green merged stack.
   - **Diff Economy**: Smallest sufficient diff satisfying all acceptance criteria without omitting tests.
