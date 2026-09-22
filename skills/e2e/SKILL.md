---
name: e2e
description: "Use when the user says /e2e, 'take this end to end', 'run the e2e flow', or asks for an approved plan-to-PR implementation. Coordinates planning, implementation, review, verification and shipping through the selected harness and execution profile."
---

# E2E — plan, approve, implement, review and ship

## Roles and execution profile

The coordinator owns context, the plan, handoffs and findings. The implementer owns code and repairs. Reviewers inspect an exact scope in fresh context; they do not repair it. These are roles, not model names.

Select routes and model identities from the task's explicit profile, arguments, or defaults:

| Setting | Supported routes |
|---|---|
| `--execution direct` (or `--direct`) | The current agent is both coordinator and implementer; independent review still uses a separate context (default) |
| `--execution codex` (or `--impl codex`, `--impl <model>`) | Dedicated implementer through `e2e-codex.sh` |
| `--execution native` | Dedicated implementer through an available, authorized native subagent facility |
| `--review codex` (or `--review <model>`) | Fresh read-only Codex consultation (default: `gpt-6-luna`) |
| `--review native` | Fresh native reviewer with enforced read-only access, when supported and authorized |

Default policy:
- Implementation defaults to `--execution direct` (in-session execution by the current coordinator model), avoiding subagent serialization latency.
- Independent adversarial review defaults to `--review codex` with `gpt-6-luna` for cross-model scrutiny. When coordinating from a Codex session running Luna, the reviewer defaults to `gpt-6-astra`.

CLI argument shorthands:
- `--direct`: Shorthand for `--execution direct`.
- `--impl <model|route>`: Set implementation route or model (e.g. `--impl direct`, `--impl astra`, `--impl codex`).
- `--review <model|route>`: Set review route or model (e.g. `--review luna`, `--review astra`, `--review native`).
- Model aliases resolve automatically: `luna` → `gpt-6-luna`, `astra` → `gpt-6-astra`, `opus` → `claude-opus-5-5`, `fable` → `claude-fable-5-1`.

Kandev, Codex, Claude Code and OpenCode are launch environments, not execution policies. Inspect actual tools and permissions. Do not choose a route from a model nickname, silently substitute self-review for independent review, or create Kandev tasks/sessions as hidden workers. Native subagents require the session's delegation authorization. If a required route is unavailable or unauthorized, report the missing capability; do not recursively invoke E2E to obtain it.

For a Codex route, read `scripts/e2e-codex.sh`. Set `E2E_IMPLEMENTER_MODEL` for implementation and `E2E_REVIEWER_MODEL` for audits/reviews to the explicitly selected model IDs; the wrapper refuses an unset identity. When not specified by the user or task profile, resolve model defaults and aliases per the policy above, or from the user's configured Codex model. Native routes record their requested model and actual model when observable. Unknown resolved identity stays unknown. Fresh context, different model and different provider are separate properties; the same model through two harnesses is not cross-model review.

The approved plan records the execution/review routes, identities, permissions and downstream actions. Changing routes must preserve these boundaries; materially different scope or permissions need a decision. A route cannot grant permissions the host or user has withheld. Only the designated implementer edits production code; in direct mode that is the current agent.

## Boundaries and dependencies

- At preflight, run `workflow-doctor` once when available on PATH; report drift warnings and refresh commands without auto-updating or adding an approval gate. If unavailable, state that local drift was not checked. This optional read-only check also works in dry-run and does not replace any required evidence.
- One plan approval gate; reuse explicit approval for the same plan/scope. Never proceed while a question is pending or manufacture approval from a timeout, turn ending or cancellation.
- Two execution failures at a stage stop the run; preserve the workspace and report the task, sessions and last error. Findings are not execution failures. Record attempts; never reset them on resume.
- Ship owns verification, publication, CI and feedback loops. No direct push/PR shortcut around ship. Merge and deployment are separate actions.
- Dependencies: native file/search/shell tools, repository guides, this plugin's ship/verify/pick-up-linear-ticket workflows, and the selected review/implementation route. Use installed brainstorming/planning skills when available; otherwise perform the planning steps below directly. Missing external integrations remain visible blockers when required.
- Read command dependencies as workflows; slash commands are not shell executables. Locate MCP capabilities by function and use the schemas actually exposed by the host.

Arguments: a ticket or task description, optional execution/review routes (e.g. `--direct`, `--impl <model>`, `--review <model>`). For a ticket, use this plugin's pick-up-linear-ticket workflow for authorized context/claim actions. For an ad-hoc task, omit ticket operations. `--dry-run` is a read-only preview: no claim/status changes, worktree provisioning, child invocation, commits, publication or completion signals; show the proposed stages and capability gaps, then stop.

## Stage 1 — Plan

1. Read the request, current task/PR ownership, repository guides and existing work. In Kandev, reuse its task/worktree and canonical plan. Load and preserve user edits to the plan before updating it.
2. Establish acceptance criteria and write a plan with task file paths, expected tests and effort: low for mechanical changes, medium for routine feature work, high for cross-cutting integration, xhigh for subtle algorithms or correctness.
3. Plan architecture, contracts, edge cases and acceptance criteria. Identify sensible increments that could be reviewed and released after their predecessors, with their purpose and dependencies. **PR boundaries are provisional** and may evolve within the approved scope/contracts. Tasks need not map one-to-one to PRs. Do not estimate or optimize for line counts during planning; ship finalizes packaging.
4. Record dependency constraints and their source. Prefer existing facilities or supported official SDKs/established libraries where they remove substantial protocol or schema plumbing. An absent manifest is not a dependency ban. Surface the cost of an explicit restriction at the plan gate; never silently override it. Small checks do not automatically need libraries.
5. Record runtime assumptions relevant to the design: lifetime, writers/processes, recovery/persistence, acceptable data loss and trust boundaries. Ephemeral/single-tenant does not imply one process or trusted input. Journals, locks, retries and supervisors require a concrete failure case; retain necessary input/filesystem protections.
6. Plan audit through the selected fresh reviewer: supply the plan, constraints and repository, ask for `READY` or `REVISE` with concrete issues and evidence. Assess sensible delivery increments and integration risks without fixed PR boundaries or line estimates.
   - **Architectural Observation Rule**: Auditors evaluate defects strictly against the approved ticket acceptance criteria and explicit repository constraints. Environmental, platform-level or host trust-boundary limitations (e.g. host identity, OS user isolation, container network access) that the ticket did not ask to change must be classified as non-blocking `Architectural Observation` for future work, never a blocking `REVISE` defect.
   - **One Audit Round Cap**: Exactly one plan audit round. The coordinator reviews findings once: accepts valid omissions/risks, rejects out-of-scope expansions with clear rationale, updates the plan, and presents both the updated plan and accepted/rejected dispositions at the human gate. Carry unresolved audit findings into the human decision. Missing/failed review is incomplete, not READY. If review permission must be obtained at the plan gate, mark the audit pending there and run it immediately after approval, before implementation. Material revisions require a decision; never label an unaudited plan READY.
7. Present the concrete plan, route/identity choices, permitted effects and audit findings. In Kandev use its plan and question tools; elsewhere use the host's supported question facility. Optional rich previews must reflect the same plan revision and must not introduce a dependency on Claude Artifacts. Ask one Approve/Revise question, unless this exact scope already has explicit approval. Observe the tool's waiting contract: pending/timeout means stop and wait; rejection means revise or end. Start implementation only after approval.

## Stage 2 — Workspace and handoff

Use branch prefix `jjholmes927-`. If `[ -f "$(git rev-parse --git-dir)/gitdir" ]`, reuse the current linked worktree, irrespective of launcher. Do not create nested worktrees. Otherwise prefer the repository's `bin/create_worktree`; use an available worktree workflow or native Git only when no project provisioner exists. Validate the repository's environment and isolated runtime, not just the checkout's existence.

Create `.e2e/` and exclude it using `git rev-parse --git-path info/exclude` (a worktree's `.git` is a file). Keep the plan local/untracked unless the user requested it committed. Use Kandev's canonical plan when present, with a revision/hash in the local handoff.

Maintain `.e2e/handoff.md` and `.e2e/sessions.tsv` with task/issue, approved plan revision and actions, source revision, routes, harness/model identity, repo/base/head/tree, runtime, stage/owner, attempts and budgets, sessions, findings/dispositions, evidence and next action. No secrets. Read these and current Git state on resume, including under another harness; verify previous external outcomes before repeating actions. A changed tree invalidates dependent evidence. Never resume past a pending decision or cancellation.

## Stage 3 — Implement each task

1. Give the implementer the approved task, neighbouring constraints, slice acceptance criteria, dependency/runtime decisions and repository guides. Include: no new explanatory/doc/rationale comments; only machine-required directives and corrections to existing stale comments. Keep one statement per line, descriptive intermediate names and guard clauses where useful. Never compress syntax, strip useful whitespace or omit tests to fit a size limit. Run configured formatting/linting and relevant tests. Do not commit in a delegated task.
2. Execute through the selected route. Codex: `scripts/e2e-codex.sh run <worktree> <effort> <prompt-file>`; capture its session. Native: send a bounded implementation brief, never `/e2e` or an instruction to orchestrate further agents. Direct: implement in this session within the approved scope. Delegated children cannot change the route or publish.
3. Record status and observed diff/tests. Nonzero failure, empty/malformed response, or no intended change without evidence the task is already satisfied: one retry with the actual error. Second execution failure stops. Missing credentials/capabilities are blockers, not reasons to burn retries or take over an unauthorized route.
4. Checkpoint only intended files; preserve unrelated work. Commit with an imperative task message and record the SHA. Native/direct implementation does not require a fictional Codex thread ID.

## Stage 4 — Implementer self-review

One self-review pass over the task commit, including relevant unchanged callers. The implementer fixes accepted findings, runs affected checks and amends the checkpoint where appropriate. Recapture SHA/tree after any edit/amend; stale identities never feed later review.

## Stage 5 — Task checkpoints and review policy

Tasks record clean checkpoints with passing tests. Do not dispatch independent reviewer subagents during active feature construction; cross-model adversarial review is consolidated at Stage 6 over the complete branch diff. (If an explicit user argument requires per-task independent review, use the selected fresh reviewer on the exact task commit with at most one fix round per task; record in handoff).

## Stage 6 — Comprehensive branch review

Use the selected fresh reviewer to check the whole branch (`base...HEAD`) against approved scope: task coverage, naming, duplication, dead code, structural readability and complexity justified by runtime/dependency constraints.
1. Require concrete severity, scenario, file/line and evidence; instruct the reviewer to try to refute each finding and verify with executable reproductions in a scratch directory where possible. Apply the **Architectural Observation Rule**: platform/infra limitations outside ticket scope are recorded as non-blocking observations, not blockers.
2. Check candidate release increments without their successors; a green final stack does not establish earlier slices' readiness.
3. One repair loop through the implementer: address valid P1/P2 findings, run affected test verification, and update the branch before PR slicing; retain remaining findings explicitly.

## Stage 7 — Ship and hand back

1. Invoke this plugin's ship workflow per PR branch in dependency order. Ship enforces both **at most 500 total added/deleted lines** against the actual base and **an incrementally releasable, understandable unit**. A PR may depend on predecessors, never on successors to restore correctness. Checkpoint commits are candidate boundaries only. No compression, omitted tests or broken intermediate states. Each slice needs its own formatting, verification, fingerprint, readiness/size gates and CI evidence. When shipping a multi-PR stack, push the branches and create PRs with their respective bases, and watch CI concurrently across the stack where supported rather than blocking sequentially. Do not stage a local plan or `.e2e/` artifacts.
2. Ship owns all CI repairs, at most three total rounds across re-entry/resume; return repairs to the selected implementer and reverify changed code. The parent's two-execution-failure stop still applies. Do not start another CI budget.
3. Carry unresolved findings visibly in the PR using the already-authorized publication route; record any posting/permission failure as outstanding rather than silently claiming completion.
4. Read back PR/head and required CI outcomes. Only then move an authorized Linear ticket to In Review, using the available integration. Never mark Done from PR readiness. Ad-hoc work has no ticket lifecycle. Failures remain blocked/in progress with the workspace and evidence preserved.
5. Report PRs, task outcomes, review/fix counts, findings, evidence gaps, identities and remaining work. No Fleet command is needed for Kandev state. Where a Kandev step requires an explicit completion signal, call the exposed `step_complete_kandev` only when that step's own criteria are evidenced and no decision/action is pending. If unavailable, report the missing handoff; never substitute a turn ending or a Review column for success.

## Codex route details

Wrapper: `${CLAUDE_PLUGIN_ROOT}/skills/e2e/scripts/e2e-codex.sh`. Use its `run`, `resume`, `review` and `audit` forms. Review/audit enforce read-only shell access; implementation uses workspace-write only within the approved route. Reviewers must not use state-changing MCP tools; disable such integrations for required read-only review. If the host cannot enforce the required boundary, block that route.

For contextual reviews use `audit` with a complete bounded brief and required result format. Native `review` is appropriate when commit/base scope supplies enough context. Resume implementation only using its recorded session and model. Model flags identify the requested model; report resolved identity only when independently observable. Do not claim provider diversity from the CLI name.
