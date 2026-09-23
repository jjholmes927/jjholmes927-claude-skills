# Multi-Agent Harness Benchmark: INT-822 Evidence Bundle Caching (v1 & v2)

**Date:** September 22–23, 2026  
**Target Repository:** [`wearebeam/interpret-investigator-agent`](https://github.com/wearebeam/interpret-investigator-agent)  
**Ticket:** [INT-822](https://linear.app/beam/issue/INT-822) — *Shared evidence bundle caching for Interpret investigator agent*  
**Parent Project:** [TALK-986](https://linear.app/beamazing/issue/TALK-986) — *Refactor the Interpret agent architecture into a shared runner*  
**Harnesses Evaluated:** Cursor Desktop, Claude Code (CLI), OpenCode, Codex CLI  
**Workflow Engine:** `joel-workflow` (migrated from v2.16.0 → v2.20.2 → v2.20.3 → v2.20.4)

---

## 1. Context & Benchmark Objective

The Interpret incident investigator agent runs in containerized environments to triage and diagnose conversation failures across production. Historically, each agent run fetched multi-megabyte payloads (Honeycomb spans, BigQuery telemetry, and audio trace bundles) multiple times per incident, generating redundant API load, rate-limiting failures, and latency spikes.

Under **TALK-986**, the team planned to extract a shared runner architecture for both Interpret and Talk agent flows. Ticket **INT-822** was selected as a realistic, non-trivial benchmark problem:
* It requires architectural design (CLI fetcher, shared filesystem cache, loopback MCP server, runner integration).
* It enforces strict incremental delivery (multi-PR stack budgeted at $\le 500$ lines per PR).
* It tests tool integration, process isolation, IPC, and unit testing under concurrency and error conditions.

### The Canonical Benchmark Prompt
To eliminate prompt drift, all runs across all harnesses were invoked with the exact same prompt:
```text
/e2e INT-822
Use TALK-986 and its linked delivery plan as the architecture context.
Implement only INT-822 in this run, preserving Interpret behavior.
Carry bundle caching into the planned shared-runner architecture.
Keep TALK-986 open as the coordination parent.
```

The benchmark was executed in two major phases: **v1** (exploratory baseline across harnesses) and **v2** (evaluating workflow remediations and model permutations).

---

## 2. Phase 1 (v1): Baseline Exploration & Pathology Discovery

On the morning of September 22, 2026, the identical prompt was dispatched across three distinct harnesses running under `joel-workflow` v2.16.0:
1. **Codex CLI v1** (GPT-6 Astra / Sol implementer)
2. **Claude Code v1** (Claude Fable coordinator + Codex Sol headless implementer)
3. **OpenCode v1** (GPT-6 Astra coordinator & implementer)

### Summary of v1 Pull Requests
- **Codex v1**: 3 PRs ([#26](https://github.com/wearebeam/interpret-investigator-agent/pull/26), [#27](https://github.com/wearebeam/interpret-investigator-agent/pull/27), [#28](https://github.com/wearebeam/interpret-investigator-agent/pull/28))
- **Claude Code v1**: 2 PRs ([#30](https://github.com/wearebeam/interpret-investigator-agent/pull/30), [#31](https://github.com/wearebeam/interpret-investigator-agent/pull/31))
- **OpenCode v1**: Stalled during multi-PR delivery and review synchronization; failed to produce a complete releasable stack.

### What v1 Revealed

#### A. Architecture & Code Slicing Variance
* **Codex v1**: Exhibited the cleanest modular slicing. It naturally broke the problem into 3 discrete layers: (1) shared cache store, (2) verified evidence tools, and (3) pre-investigation runner wiring. However, its test suite lacked depth on boundary failure modes (corrupted cache JSON, concurrent writers, network timeouts).
* **Claude Code v1**: Compressed the entire solution into only 2 PRs. It suffered from notable code duplication—implementing a third redundant copy of the stdio JSON-RPC MCP envelope instead of reusing existing helpers in `mcp/slack-server.mjs` and `mcp/linear-server.mjs`.
* **OpenCode v1**: Had difficulty managing the git worktree lifecycle and Kandev PR publishing commands, highlighting gaps in harness portability.

#### B. Workflow & Harness Friction in v1
A deep audit of the v1 runs exposed critical systemic flaws in the existing `joel-workflow` v2.16.0 pipeline:
1. **Model Name Hardcoding**: `/e2e` hardcoded Fable as the sole planner and Sol (Codex) as the sole implementer, making it brittle when run under other harnesses (OpenCode, Codex CLI, Cursor).
2. **The Subagent Serialization Penalty**: For every individual task in the plan, the coordinator serialized prompts to disk, spawned `e2e-codex.sh`, captured JSONL logs, and parsed output. This added 3–5 minutes of idle wrapper overhead per task even when code generation was instantaneous.
3. **Inner-Loop Reviewer Pauses**: `/e2e` dispatched an independent reviewer subagent after *every single task commit*. This forced constant context re-loading and resulted in excessive review latency for routine, mechanical code.
4. **Multi-PR Delivery Delays**: `ship.md` enforced a mandatory 3-minute review-bot polling delay on intermediate stack PRs, causing multi-PR delivery to drag out needlessly.

---

## 3. What We Changed in Between (v1 → v2 Evolution)

Between v1 and v2, we redesigned the workflow to eliminate artificial harness friction, improve cross-model portability, and accelerate delivery. These changes were packaged and published as **`joel-workflow` v2.20.2 → v2.20.4**:

| Dimension | v1 Approach (`joel-workflow` 2.16) | v2 Approach (`joel-workflow` 2.20.4) | Why Changed |
|---|---|---|---|
| **Execution Policy** | Mandatory headless subagent delegation (`e2e-codex.sh`) per task | Direct in-session implementation by default (`--execution direct`) | Eliminates JSON-RPC/file IPC overhead and context serialization lag. |
| **Execution Roles** | Hardcoded model nicknames (`fable`, `sol`) | Abstract roles: `Coordinator`, `Implementer`, `Reviewer` | Allows any model or harness (Cursor, OpenCode, Codex, Claude) to fill any role. |
| **Review Timing** | Inner loop: Independent subagent review dispatched after *every task* | Consolidated: Stage-6 branch diff review (`base...HEAD`) | Stops constant stop-and-go review cycles on intermediate WIP commits. |
| **Plan Audit Cap** | Unbounded multi-round debate between planner & auditor | Strict 1-round audit cap; coordinator presents dispositions at human gate | Prevents infinite planning loops and scope expansion before coding starts. |
| **Review Scope Bounds** | Unconstrained adversarial scrutiny | **Architectural Observation Rule**: Platform/infra limits logged as non-blocking | Stops reviewers from blocking application PRs on preexisting container/host security limitations. |
| **Model Shorthands** | Rigid environment variable flags | Added `--direct`, `--impl <model>`, `--review <model>` with automatic alias resolution | Simplifies orchestrating cross-model bake-offs (e.g. `--review luna`). |
| **Stack Delivery** | 3-minute bot polling pause on each PR in a stack | Stack-aware delivery; skip bot pauses on intermediate PRs; async merge handling | Prevents multi-PR delivery from blocking on intermediate dependencies. |

---

## 4. Phase 2 (v2): The Multi-Agent Bake-Off

With the updated workflow in place, we re-ran the identical INT-822 prompt across four harness and model topologies on the evening of September 22:

1. **Codex CLI v2**: Sol/Astra headless execution ([PRs #33–#35](https://github.com/wearebeam/interpret-investigator-agent/pull/33))
2. **OpenCode v2**: GPT-6 Astra coordinator/implementer ([PRs #36–#40](https://github.com/wearebeam/interpret-investigator-agent/pull/36))
3. **Claude Code v2**: Fable coordinator + Codex Astra implementer/adversary ([PRs #41–#45](https://github.com/wearebeam/interpret-investigator-agent/pull/41))
4. **Cursor (Winner)**: Opus 5.5 direct coordinator/implementer + GPT-6 Luna reviewer ([PRs #46–#48](https://github.com/wearebeam/interpret-investigator-agent/pull/46))

### Cross-Harness Comparison Matrix (v2)

| Metric | Cursor (Winner) | Claude Code v2 | OpenCode v2 | Codex CLI v2 |
|---|---|---|---|---|
| **Topology** | In-session direct authoring + out-of-band review | Dual-agent coordinator + headless implementer/auditor | Headless coordinator/implementer | Single-agent CLI worktree flow |
| **Coordinator** | Claude 3.5 Opus / Opus 5.5 (`opus[1m]`) | Claude Fable (`fable[1m]`) | GPT-6 Astra (`openai/gpt-6-astra`) | GPT-5.6 Sol / GPT-6 Astra |
| **Implementer** | Opus 5.5 (in-session direct) | Codex Astra (`gpt-6-astra`) | GPT-6 Astra | GPT-5.6 Sol |
| **Reviewer** | GPT-6 Luna (`gpt-6-luna`) | Codex Astra (`gpt-6-astra`) | GPT-6 Astra (self/audit) | Sol / Astra |
| **PR Output** | **3 clean PRs** ([#46](https://github.com/wearebeam/interpret-investigator-agent/pull/46), [#47](https://github.com/wearebeam/interpret-investigator-agent/pull/47), [#48](https://github.com/wearebeam/interpret-investigator-agent/pull/48)) | 5 PRs ([#41](https://github.com/wearebeam/interpret-investigator-agent/pull/41)–[#45](https://github.com/wearebeam/interpret-investigator-agent/pull/45)) | 5 PRs ([#36](https://github.com/wearebeam/interpret-investigator-agent/pull/36)–[#40](https://github.com/wearebeam/interpret-investigator-agent/pull/40)) | 3 PRs ([#33](https://github.com/wearebeam/interpret-investigator-agent/pull/33)–[#35](https://github.com/wearebeam/interpret-investigator-agent/pull/35)) |
| **Outcome** | **Merged cleanly to `main`** | Closed (scope creep) | Closed (review idle) | Closed (superseded) |
| **Total Wall-Clock** | **~28 minutes** | ~115 minutes | ~65 minutes | ~42 minutes |
| **Dominant Latency** | Active code authoring & verify | **85m+ debate on host container UID security** | **45m spent across 4 clean reviews** | Manual stack stitching & CLI polling |

---

## 5. Detailed Failure Mode Analysis in v2

### A. The "Adversarial Tax" & Scope Creep: Claude Code v2 (Fable + Astra)
In the Claude Code v2 run, implementation of the initial cache logic was fast and accurate. However, during adversarial review:
* Astra identified that running the agent within the existing runner container gave the agent process read access to container environment variables.
* Fable accepted this as a blocking defect and expanded task scope into modifying container user permissions.
* The two agents spent **85 minutes** arguing about Docker UID namespaces, user switching, and file permissions, eventually authoring [PR #45](https://github.com/wearebeam/interpret-investigator-agent/pull/45) (*"Run Claude as a separate user so it cannot read harness secrets"*).
* **Impact**: Blew out the ticket scope from 3 PRs to 5 PRs, wasted millions of tokens, and stalled delivery on platform infrastructure outside INT-822.

### B. Redundant Review Ceremony: OpenCode v2 (GPT-6 Astra)
* OpenCode v2 successfully authored modular code across 5 PRs.
* However, OpenCode's internal harness mechanics triggered redundant audit routines after every stage.
* 4 consecutive review cycles returned `READY` (0 defects found), yet each review required full context re-hydration and prompt processing.
* **Impact**: **45 minutes** of pure idle wait time for reviews that generated zero actionable diff changes.

### C. The Winning Formula: Cursor (Opus 5.5 + Luna)
* **Direct Execution**: Opus 5.5 implemented the 3-PR stack in-session without subagent serialization delay. It adhered strictly to the repository conventions and shared existing MCP patterns.
* **Sharp, Non-Blocking Cross-Model Review**: Luna (`gpt-6-luna`) reviewed the complete branch diff (`base...HEAD`). Luna identified genuine boundary conditions (cache corruption recovery, handling partial JSON streams) without hallucinating infrastructure requirements.
* **Outcome**: 3 PRs ([#46](https://github.com/wearebeam/interpret-investigator-agent/pull/46), [#47](https://github.com/wearebeam/interpret-investigator-agent/pull/47), [#48](https://github.com/wearebeam/interpret-investigator-agent/pull/48)) merged cleanly in order to `main` with green CI.

---

## 6. Key Learnings & Strategic Takeaways

1. **Raw Code Generation is Solved; Review Protocol is the Bottleneck**: Across all v1 and v2 runs, writing Python/JS code and running tests took <20% of wall-clock time. Multi-agent debate loops and subagent IPC accounted for >80% of latency.
2. **Unconstrained Adversarial Loops Attack Trust Boundaries**: When given open-ended instructions to find defects, models inevitably attack the environment, host operating system, or platform security model rather than ticket acceptance criteria. The **Architectural Observation Rule** is essential to keep agents on track.
3. **Cross-Model Review is Superior to Self-Review**: Opus 5.5 + Luna 6 provided the highest signal-to-noise ratio. Luna caught real concurrency and cache-invalidation edge cases that Opus missed, while avoiding the dogmatic rabbit holes that Astra fell into.
4. **Direct Execution Trumps Subagent Chains**: For tasks of moderate complexity, in-session direct implementation by a frontier model (Opus 5.5) consistently beats multi-subagent pipelines by avoiding serialization loss and IPC friction.

---

## 7. Playbook for Future Model & Harness Bake-Offs

When benchmarking future model generations (e.g. testing next-gen Opus, GPT-6 iterations, or local open-weights models) or new agent harnesses:

1. **Task Selection**:
   - Must be a multi-PR distributed system task with external protocol integration (e.g. MCP, CLI, REST) and architectural dependencies. Avoid toy algorithmic problems.
2. **Execution Standardization**:
   - Use the canonical prompt format linking parent coordination issues and explicit acceptance criteria.
   - Run in an isolated git worktree via `kandev_worktree_setup.sh`.
3. **Telemetry Tracking**:
   - Record exact wall-clock timestamps for:
     1. Planning completion & Human gate (`t_plan`)
     2. Task implementation completion (`t_impl`)
     3. Review and repair loop (`t_review`)
     4. Publication and CI verification (`t_ship`)
4. **Evaluation Metrics**:
   - **Signal-to-Noise Ratio (SNR)**: Valid defects caught vs out-of-scope/hallucinated blockers.
   - **Diff Economy**: Smallest sufficient diff satisfying acceptance criteria without stripping tests.
   - **Wall-Clock Latency**: Time to green merged stack.
