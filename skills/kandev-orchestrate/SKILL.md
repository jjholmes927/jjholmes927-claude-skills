---
name: kandev-orchestrate
description: "Use when the user asks to orchestrate, sequence, or dispatch waves of tickets across repositories in Kandev (e.g. /kandev-orchestrate, 'orchestrate these tickets in Kandev', 'run wave orchestration for TALK-986', 'dispatch tickets across worktrees in waves'). Replaces legacy tmux orchestrating-lanes."
---

# Kandev Orchestrate — Multi-Repo Wave Orchestration

## Overview

Coordinates multi-ticket, multi-repo implementation waves across independent Kandev sessions.

The orchestrator owns:
- Validating tickets in Linear and discovering target repositories.
- Structuring the topological dependency graph (DAG) into discrete waves.
- Creating Kandev tasks using worktree execution (`exec-worktree`).
- Chaining wave dependencies with `blocked_by` and `start_when_unblocked: true`.
- Presenting a clean, real-time status dashboard.

**The orchestrator does not write production code, approve implementation plans, or merge pull requests.** Each task runs an independent worker session that owns its worktree and reports directly to the user at human approval gates.

---

## Boundaries and Roles

```
┌────────────────────────────────────────────────────────┐
│               Orchestrator Session                     │
│  - Plans wave DAG                                      │
│  - Calls Kandev MCP tools                              │
│  - Monitors progress & renders dashboard               │
└───────────┬────────────────────────────────┬───────────┘
            │ creates tasks                  │ creates tasks
            ▼ (Wave 1: start_agent=true)     ▼ (Wave 2+: blocked_by, start_when_unblocked=true)
┌───────────────────────────┐    ┌───────────────────────────┐
│ Kandev Worker (Repo A)    │    │ Kandev Worker (Repo B)    │
│  - Runs /e2e <TICKET>     │    │  - Dormant until Wave 1   │
│  - Owns isolated worktree │    │    tasks complete         │
│  - User approves plan (T1)│    │  - Runs /e2e <TICKET>     │
│  - Opens PR <500 lines    │    │  - User approves plan (T1)│
│  - User merges PR (T2)    │    │  - Opens PR <500 lines    │
└───────────────────────────┘    └───────────────────────────┘
```

### The Two Human Touchpoints
Worker sessions run `/e2e <TICKET> --execution direct --review luna`. They require human interaction at two points:
1. **Touchpoint 1 — Plan Approval**: The worker posts its implementation plan and waits for approval. The user approves or amends directly in the worker session. The orchestrator **never** auto-approves plans.
2. **Touchpoint 2 — PR Review & Merge**: The worker verifies changes, runs Luna adversarial review, opens a PR (<500 lines), and moves the ticket to In Review. The user merges the PR.

Kandev considers a task complete when its session finishes cleanly and PR automation requirements are satisfied, unblocking downstream tasks.

---

## Scoping and Wave Rules ($N$-Waves)

### Scoping Rules
1. Never sweep an entire team backlog or Todo column without explicit user confirmation.
2. Support two input formats:
   - **Parent Ticket / Epic**: e.g. `/kandev-orchestrate TALK-986`. Read the parent ticket and its linked delivery plan/sub-issues in Linear.
   - **Explicit Ticket List**: e.g. `/kandev-orchestrate TALK-998 TALK-1007 then TALK-997 TALK-1006`.
3. Verify every ticket in Linear: confirm title, assignee, state, and target repository.

### Wave Decomposition ($N$-Waves)
A wave is an independent tier in the topological execution graph.

| Relationship | Execution Strategy | Criteria |
|---|---|---|
| **Same Wave (Parallel)** | Sibling tasks launched at the same time | Disjoint blast radius (different files or different repos), independent base branches from `origin/main`, no shared schema migrations or contract coupling. |
| **Next Wave (`blocked_by`)** | Deferred launch via Kandev DAG | Interface/type dependency (Consumer calls Producer), file collision (both edit core router/engine files), cross-repo producer/consumer, or database migration dependency. |

#### Confirmation Gate
Before creating any Kandev tasks, display the proposed wave plan and wait for user approval:

```markdown
### Proposed Execution Plan for TALK-986

| Wave | Repo | Ticket | Title | Depends On |
|---|---|---|---|---|
| 1 | interpret-investigator-agent | TALK-998 | Extract shared runner contracts | None (Immediate) |
| 1 | magicnotes | TALK-1007 | Resolve call-time config for Talk | None (Immediate) |
| 2 | interpret-investigator-agent | TALK-997 | Keep investigation content out of logs | TALK-998 |
| 2 | magicnotes | TALK-1006 | Expose Talk evidence bundle endpoint | TALK-1007 |

Dispatch this wave plan?
```

---

## Kandev Dispatch Protocol

Once confirmed, dispatch tasks using Kandev MCP tools:

### 1. Discover Environment IDs
- Call `list_workspaces_kandev` to get the workspace ID (e.g. `Default Workspace`).
- Call `list_workflows_kandev` to get the target workflow ID (e.g. `Development`).
- Call `list_agents_kandev` to resolve the Claude ACP agent profile ID (`opus[1m]`).
- Call `list_executor_profiles_kandev` with `executor_id: "exec-worktree"` to get the worktree executor profile ID.

### 2. Format Worker Prompts
Every worker receives an explicit, self-contained launch prompt:

```text
/e2e <TICKET_KEY> --execution direct --review luna
Use <PARENT_KEY> and its linked delivery plan as the architecture context.
Implement only <TICKET_KEY> in this run.
<SPECIFIC_TASK_GOAL>
Keep PRs under 500 lines.
Follow the Architectural Observation Rule (log platform/host trust limits as non-blocking notes, not blocking defects).
```

### 3. Create Wave Tasks
- **Wave 1 Tasks (Immediate):**
  Call `create_task_kandev`:
  ```json
  {
    "title": "<TICKET_KEY>: <Short Summary>",
    "workspace_id": "<WORKSPACE_ID>",
    "workflow_id": "<WORKFLOW_ID>",
    "agent_profile_id": "<CLAUDE_ACP_PROFILE_ID>",
    "executor_profile_id": "<WORKTREE_PROFILE_ID>",
    "local_path": "<LOCAL_REPO_PATH>",
    "start_agent": true,
    "prompt": "<FORMATTED_PROMPT>"
  }
  ```
  Record returned task IDs.

- **Wave 2+ Tasks (Chained via `blocked_by`):**
  Call `create_task_kandev` with dependencies:
  ```json
  {
    "title": "<TICKET_KEY>: <Short Summary>",
    "workspace_id": "<WORKSPACE_ID>",
    "workflow_id": "<WORKFLOW_ID>",
    "agent_profile_id": "<CLAUDE_ACP_PROFILE_ID>",
    "executor_profile_id": "<WORKTREE_PROFILE_ID>",
    "local_path": "<LOCAL_REPO_PATH>",
    "blocked_by": ["<PREDECESSOR_TASK_ID>"],
    "start_when_unblocked": true,
    "start_agent": true,
    "prompt": "<FORMATTED_PROMPT>"
  }
  ```
  *Note: Setting `start_agent: true` with `blocked_by` and `start_when_unblocked: true` safely registers the launch prompt without starting until dependencies resolve.*

---

## Status Monitoring & Dashboard

Monitor active waves periodically using `list_tasks_kandev`, `list_related_tasks_kandev`, and `get_task_conversation_kandev`.

### Dashboard Format
Report task health with clear indicators for required human action:

```markdown
### Wave Status Dashboard

| Wave | Repo | Ticket | Kandev Task | State | Action Needed |
|---|---|---|---|---|---|
| 1 | investigator | TALK-998 | `087b5441...` | RUNNING | 🟡 Plan approval pending (Touchpoint 1) |
| 1 | magicnotes | TALK-1007 | `f6c967e6...` | RUNNING | 🟢 Coding / Luna review in progress |
| 2 | investigator | TALK-997 | `08f142c7...` | BLOCKED | ⏳ Waiting on Wave 1 (TALK-998) |
| 2 | magicnotes | TALK-1006 | `3577b026...` | BLOCKED | ⏳ Waiting on Wave 1 (TALK-1007) |
```

### State Indicators
- 🟡 **Touchpoint 1 (Plan Approval)**: Worker is waiting on user question/plan sign-off. Notify user with task ID and session link.
- 🟣 **Touchpoint 2 (PR Review)**: PR opened (<500 lines), tests passed, waiting on user merge.
- 🟢 **Active / Implementing**: Worker is coding, running tests, or executing Luna review.
- ⏳ **Blocked / Deferred**: Task is waiting on preceding wave in Kandev DAG.
- 🔴 **Failed / Paused**: A task encountered an unrecoverable failure or was cancelled. Kandev halts dependent downstream tasks to prevent cascading errors. Human intervention required.

---

## Wave Transitions and Failures

1. **Automatic Unblocking**: When all predecessor tasks in Wave $k$ merge and complete, Kandev unblocks Wave $k+1$. The orchestrator detects this transition, reports it to the user, and begins monitoring the new wave.
2. **Predecessor Failure**: If a task fails or its PR is rejected:
   - Downstream dependent tasks remain safely blocked.
   - The orchestrator alerts the user with the failed task ID and the last error message from `get_task_conversation_kandev`.
   - Once resolved manually or restarted via `spawn_session_kandev`, the dependency clears upon completion.
3. **Stale Deferred Prompts**: If implementation discoveries in Wave 1 alter requirements for Wave 2 before Wave 2 starts, update the deferred prompt using `update_task_kandev` with `deferred_launch_prompt`.

---

## Mid-Flow DAG Mutation & Dependency Changes

Decisions change during plan reviews and implementation (e.g. a reviewer notices shared MCP plumbing and spins off a new ticket, or scope is split). Because Kandev stores tasks and edges in a durable database, the orchestrator can mutate the execution graph live while earlier waves are still running.

### 1. Ingesting a New Ticket Mid-Flight
When a ticket is inserted (e.g. `TALK-1018: Extract shared MCP SDK`):
1. **Identify its DAG placement**:
   - What must complete before it can start? (e.g. `blocked_by: [TALK-998]`)
   - What unstarted downstream tasks must now wait for it? (e.g. `TALK-1006` or `TALK-997`)
2. **Create the Kandev task**:
   Call `create_task_kandev` with:
   - `blocked_by: ["<PREDECESSOR_TASK_ID>"]`
   - `start_when_unblocked: true`
   - `start_agent: true`
   - Formatted `/e2e` prompt referencing the parent architecture.
3. **Rewire downstream dependencies**:
   For each downstream task that now depends on the new task:
   - Call `add_task_dependency_kandev(task_id: downstream_id, depends_on_task_id: new_task_id)`.
   - If an old dependency edge is strictly replaced (rather than augmented), call `remove_task_dependency_kandev`.
   - *Note on Orchestrator Scope:* If the MCP dependency tools enforce current-task scoping, use Kandev's local HTTP API endpoints directly:
     - Add edge: `POST http://127.0.0.1:38429/api/v1/tasks/<downstream_id>/dependencies` with `{"depends_on_task_id": "<new_task_id>"}`.
     - Remove edge: `DELETE http://127.0.0.1:38429/api/v1/tasks/<downstream_id>/dependencies/<old_predecessor_id>`.
4. **Refresh deferred launch prompts**:
   For any unstarted downstream task whose prompt assumed the old architecture, update its prompt and description so worker agents wake up with current architectural assumptions:
   ```json
   update_task_kandev({
     "task_id": "<DOWNSTREAM_TASK_ID>",
     "description": "<UPDATED_PROMPT_REFERENCING_NEW_TICKET>"
   })
   ```
5. **Re-render the Dashboard**:
   Update the wave status table to show the new task and the re-tiered wave structure.

