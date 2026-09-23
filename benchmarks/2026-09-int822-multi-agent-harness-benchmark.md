# Multi-Agent Benchmark: INT-822 Evidence Bundle Caching (v1 & v2)

> **TL;DR:** We benchmarked 4 agent harnesses on a real, multi-PR caching ticket ([INT-822](https://linear.app/beam/issue/INT-822)). In v1, our own workflow got in the way—spawning subagents and running adversarial review after every commit wasted hours. After fixing the workflow for v2, **Cursor (Opus 5.5 + Luna review) won in 28 minutes**, delivering 3 clean PRs ([#46](https://github.com/wearebeam/interpret-investigator-agent/pull/46), [#47](https://github.com/wearebeam/interpret-investigator-agent/pull/47), [#48](https://github.com/wearebeam/interpret-investigator-agent/pull/48)) that merged straight to `main`. Unconstrained review was the biggest time-sink across all runs: Claude Code burned 85 minutes arguing about Docker permissions instead of writing code.

---

## What We Tested

* **Target Repo:** [`wearebeam/interpret-investigator-agent`](https://github.com/wearebeam/interpret-investigator-agent)
* **Ticket:** [INT-822](https://linear.app/beam/issue/INT-822) (under parent [TALK-986](https://linear.app/beamazing/issue/TALK-986))
* **The Problem:** The incident investigator agent repeatedly fetched multi-megabyte payloads (Honeycomb spans, BigQuery logs, audio traces) for the same incident, hitting rate limits and adding latency.
* **The Task:** Build a shared disk cache, wrap it in a local MCP server, wire it into the runner, and ship it as a clean stack of PRs ($\le 500$ lines each).
* **Harnesses:** Cursor Desktop, Claude Code CLI, OpenCode, Codex CLI.

### The Benchmark Prompt
Every harness received this exact prompt:
```text
/e2e INT-822
Use TALK-986 and its linked delivery plan as the architecture context.
Implement only INT-822 in this run, preserving Interpret behavior.
Carry bundle caching into the planned shared-runner architecture.
Keep TALK-986 open as the coordination parent.
```

---

## Phase 1 (v1): What Happened in the Baseline

On the morning of September 22, 2026, we ran the prompt across three harnesses using `joel-workflow` v2.16.0:
1. **Codex CLI v1** (GPT-6 Astra / Sol) → 3 PRs ([#26](https://github.com/wearebeam/interpret-investigator-agent/pull/26), [#27](https://github.com/wearebeam/interpret-investigator-agent/pull/27), [#28](https://github.com/wearebeam/interpret-investigator-agent/pull/28))
2. **Claude Code v1** (Fable coordinator + Codex Sol implementer) → 2 PRs ([#30](https://github.com/wearebeam/interpret-investigator-agent/pull/30), [#31](https://github.com/wearebeam/interpret-investigator-agent/pull/31))
3. **OpenCode v1** (GPT-6 Astra) → Stalled on git worktrees and PR publishing.

### How Each Model Built the Code
* **Codex v1** sliced the problem cleanly into 3 layers: cache store, evidence tools, and runner integration. But it missed basic failure tests (corrupted cache files, concurrent writes, network drops).
* **Claude Code v1** squashed everything into 2 PRs and pasted a duplicate copy of the stdio JSON-RPC MCP envelope instead of reusing existing helpers.
* **OpenCode v1** tripped over git worktrees and couldn't finish delivering the stack.

### What Was Slowing Down Our Workflow
The models weren't the real problem in v1. Our own workflow was:
1. **Hardcoded model names:** `/e2e` only knew "fable" and "sol", so running another model was brittle.
2. **Subagents wasted 3–5 minutes per task:** Spawning a headless subagent for every task added minutes of disk and process overhead, even when the code took seconds to write.
3. **Reviewing every commit killed momentum:** Running an adversarial review after every single task commit caused constant stop-and-go friction.
4. **Stacked PR delays:** `ship` forced a 3-minute wait for bot reviews on intermediate PRs, dragging delivery out for hours.

---

## What We Changed Between v1 and v2

We overhauled `joel-workflow` (v2.16.0 → v2.20.4) before running the bake-off again:

| Area | v1 (`joel-workflow` 2.16) | v2 (`joel-workflow` 2.20.4) | Why |
|---|---|---|---|
| **Execution** | Headless subagent per task | Direct in-session (`--execution direct`) | Cuts 3–5 min process startup per task. |
| **Roles** | Hardcoded model nicknames (`fable`, `sol`) | Abstract roles (`Coordinator`, `Implementer`, `Reviewer`) | Any model/harness can fill any role. |
| **Review Timing** | After every task commit | Consolidated branch diff review at Stage 6 | Stops review thrash on unfinished WIP commits. |
| **Plan Audits** | Endless debate rounds | Capped at 1 round; human gate decides | Stops agents arguing over plans before coding. |
| **Review Scope** | Anything goes | **Architectural Observation Rule** | Flags host/container security as notes, not blockers. |
| **Stack Delivery** | 3-minute pause per PR | Fast stack shipping; skip pauses on middle PRs | Intermediate PRs don't block the stack. |

---

## Phase 2 (v2): The Bake-Off

We re-ran the identical prompt with the updated workflow across four setups:

| Metric | Cursor (Winner) | Claude Code v2 | OpenCode v2 | Codex CLI v2 |
|---|---|---|---|---|
| **Setup** | In-session direct + out-of-band review | Dual-agent coordinator + subagent reviewer | Headless coordinator/implementer | Single-agent CLI worktree flow |
| **Coordinator** | Opus 5.5 (`opus[1m]`) | Claude Fable (`fable[1m]`) | GPT-6 Astra | GPT-5.6 Sol / GPT-6 Astra |
| **Implementer** | Opus 5.5 (direct in-session) | Codex Astra (`gpt-6-astra`) | GPT-6 Astra | GPT-5.6 Sol |
| **Reviewer** | GPT-6 Luna (`gpt-6-luna`) | Codex Astra (`gpt-6-astra`) | GPT-6 Astra (self-audit) | Sol / Astra |
| **PR Output** | **3 clean PRs** ([#46](https://github.com/wearebeam/interpret-investigator-agent/pull/46), [#47](https://github.com/wearebeam/interpret-investigator-agent/pull/47), [#48](https://github.com/wearebeam/interpret-investigator-agent/pull/48)) | 5 PRs ([#41](https://github.com/wearebeam/interpret-investigator-agent/pull/41)–[#45](https://github.com/wearebeam/interpret-investigator-agent/pull/45)) | 5 PRs ([#36](https://github.com/wearebeam/interpret-investigator-agent/pull/36)–[#40](https://github.com/wearebeam/interpret-investigator-agent/pull/40)) | 3 PRs ([#33](https://github.com/wearebeam/interpret-investigator-agent/pull/33)–[#35](https://github.com/wearebeam/interpret-investigator-agent/pull/35)) |
| **Result** | **Merged cleanly to `main`** | Closed (scope creep) | Closed (review idle) | Closed (superseded) |
| **Total Time** | **28 minutes** | 115 minutes | 65 minutes | 42 minutes |
| **Where Time Went** | Writing code & running tests | **85 min debating Docker UID permissions** | **45 min running 4 clean reviews** | Manual stack stitching & CLI polling |

---

## What Broke and What Worked in v2

### 1. Claude Code v2: The Review Rabbit Hole (85 min wasted)
Claude Code wrote good caching code quickly. But during review, Astra noticed the agent ran as the same user as the container and could read environment variables. Fable treated this as a blocking bug. 
The two agents spent 85 minutes debating Docker user permissions and authoring an out-of-scope PR ([PR #45](https://github.com/wearebeam/interpret-investigator-agent/pull/45)). A 3-PR ticket blew out to 5 PRs and burned millions of tokens on infrastructure that had nothing to do with INT-822.

### 2. OpenCode v2: 45 Minutes of Empty Reviews
OpenCode wrote modular code across 5 PRs, but its harness ran redundant review cycles after every step. Four reviews in a row came back clean (`READY`, 0 defects), but each pass took 10+ minutes to re-read files and process prompts. 45 minutes were lost waiting for reviews that changed nothing.

### 3. Cursor (Opus 5.5 + Luna): The Winning Combo (28 min total)
* **Direct authoring:** Opus 5.5 wrote the 3 PRs directly in the session. No subagent startup delays, no lost context, and clean reuse of existing repo helpers.
* **Sharp cross-model review:** Luna reviewed the final branch diff (`base...HEAD`). Luna caught real edge cases (cache corruption, partial JSON streams) without inventing platform security requirements.
* **Outcome:** Clean 3-PR stack merged straight to `main` with green CI.

---

## Key Takeaways

1. **Writing code is fast; reviews are the bottleneck.** Writing code and running unit tests took under 20% of the total time. Review loops and subagent startup took more than 80%.
2. **Uncapped reviews attack platform boundaries.** If you give a reviewer an open-ended goal to "find bugs", it will attack the host machine, container security, or OS settings instead of the ticket. The **Architectural Observation Rule** keeps reviewers on topic.
3. **Cross-model review beats self-review.** Opus 5.5 writing code and Luna 6 reviewing it gave the best results. Luna found genuine concurrency bugs that Opus missed, without going down Astra's rabbit holes.
4. **In-session coding beats subagents.** Spawning subagents for simple tasks adds latency and loses nuance. A strong frontier model (Opus 5.5) working directly in-session is faster and cleaner.

---

## How to Run Future Bake-Offs

When testing new models or harnesses:

1. **Pick the right task:** Use a multi-PR stack with external tools (MCP, CLI, APIs). Don't use toy one-file tasks.
2. **Keep the prompt identical:** Use the standard `/e2e <TICKET>` prompt with clear parent ticket context.
3. **Track real milestones:**
   * `t_plan`: Plan approved at human gate
   * `t_impl`: Code written and tests passing
   * `t_review`: Review feedback resolved
   * `t_ship`: PRs opened and merged
4. **Judge on three things:**
   * **Signal-to-noise:** Did the reviewer catch real bugs, or hallucinate platform problems?
   * **PR quality:** Small, clean PRs with good tests vs. bloated diffs.
   * **Wall-clock time:** Time from prompt to merged code.
