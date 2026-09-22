---
name: e2e
description: "Use when the user says /e2e, 'take this end to end', 'run the e2e flow', or gives a ticket/prompt to fully implement hands-off. Runs the plan→approve-once→implement→review→ship pipeline where Fable plans, Sol (codex) writes all code headlessly, and both review."
---

# e2e — Fable plans, Sol implements, both review

Wrapper script: `${CLAUDE_PLUGIN_ROOT}/skills/e2e/scripts/e2e-codex.sh`
(`run <workdir> <effort> <prompt-file>` → prints codex thread id; `resume <workdir> <thread-id> <effort> <prompt-file>`; `review <workdir> [--commit <sha>|--base <branch>|--uncommitted]`; `audit <workdir> <prompt-file>` → read-only sandbox, prints Sol's verdict)

## Iron Laws

Violating the letter of a law is violating the law — there is no spirit-of-the-law exception.

1. **Fable never writes production code** — no exception for one-line fixes. All code goes through the wrapper to Sol.
2. **The plan gate is the only human gate** — never add or skip gates.
3. **Two failures at any stage = hard-stop and report** (worktree path, task, thread ids, last error) — never delete the worktree.

## Red Flags — STOP

- **Writing code yourself** → STOP, route it through `e2e-codex.sh` to Sol.
- **Adding a confirmation stop after plan approval** → STOP, proceed; the plan gate was the only gate.
- **Running a loop past its cap** (implement: 1 retry; Fable fix loop: 3; CI fixes: ship owns 3 total; plan audit: 2) → STOP, hard-stop and carry findings to PR comments.
- **Deleting/recreating the worktree after failure** → STOP, leave it and report its path.
- **Shipping with unresolved findings** → STOP, post each as a `[e2e unresolved]` PR comment first.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| It's a one-line fix, faster myself | All code goes through Sol — no line-count threshold |
| Sol failed twice, I'll finish it | Two failures = hard-stop and report, not takeover |
| I'll just add one more check-in with the user | The plan gate is the ONLY gate |
| Findings are minor, ship clean | Every unresolved finding becomes a PR comment |
| I'll ask Joel whether to move the ticket / mark the stream | Stage 7 step 4 decides that from CI state; asking is an interruption without a judgement call |

## When NOT to use

Trivial single-file changes, or when the user wants per-task involvement.

## Dependencies

codex CLI (authenticated), gh CLI, superpowers plugin, this plugin's ship + pick-up-linear-ticket commands.

## Arguments

- `/e2e INT-123` — Linear ticket: first invoke joel-workflow pick-up-linear-ticket for context and status moves.
- `/e2e "<task description>"` — ad-hoc prompt.
- `--dry-run` anywhere in the args: run stages 1–2 normally, then print every wrapper/gh/ship command verbatim instead of executing it, write nothing outside `.e2e/`, and stop before ship. Recommended on first use in a new repo.

## Stage 1 — Plan (Fable)

1. If the argument is a Linear ticket id, invoke the pick-up-linear-ticket command from this plugin first.
2. Invoke superpowers:brainstorming (keep it brief for small, well-specified tasks), then superpowers:writing-plans.
3. The plan MUST give each task: exact file paths, test expectations, and an **effort grade** by task complexity (not project importance):

   | Task shape | Grade |
   |------------|-------|
   | Touches 1–2 files, fully specified, mechanical | low |
   | Routine feature code, clear pattern to follow | medium |
   | Cross-cutting or multi-file integration | high |
   | Algorithmic, subtle correctness, or tricky domain logic | xhigh |

   Plan the architecture, contracts, edge cases and acceptance criteria. Identify sensible increments that could be reviewed and released after their predecessors, and describe their purpose and dependencies. **Treat proposed PR boundaries as provisional**; refine them as implementation reveals the actual shape of the work, while preserving the approved scope and contracts. Implementation tasks do not need to map one-to-one to PRs. Do not estimate or optimize for line counts during planning. Ship finalizes PR packaging and checks each PR's release readiness and size.

   Record the repository's dependency constraints and their source. Prefer existing facilities or supported official SDKs and established libraries when they remove substantial protocol or schema plumbing. An absent package manifest is not a dependency ban; add one when justified and permitted. If an explicit restriction forces bespoke plumbing, surface that tradeoff at the plan gate rather than silently overriding it. Choose dependencies for maintained support and compatibility, not popularity alone; small checks do not automatically need a library.

   Record the actual runtime assumptions relevant to the design: state lifetime, number of processes/writers, persistence and recovery needs, acceptable data loss, and trust boundaries. Do not assume ephemeral or single-tenant means single-process or trusted input. Journals, locks, retries and supervisors need a concrete requirement or failure case; retain necessary input and filesystem protections. Carry these constraints into implementation and review.
4. Sol plan audit (cross-model, before the human sees the plan): write the plan plus "Audit this plan for correctness, security, and completeness against the repo. Assess the proposed increments for sensible review/release boundaries and integration risks, without requiring fixed PR boundaries or line estimates. Check that dependencies and state-management complexity follow the recorded constraints. Verdict: READY, or REVISE with concrete issues." to a temp file; run `e2e-codex.sh audit <repo-root> <file>` (read-only sandbox — safe on the main checkout). On REVISE, fix the issues and re-audit. Max 2 audit rounds; if still REVISE, present the plan with the unresolved audit notes attached.
5. Present the plan at the gate:
   - If the plan touches anything user-facing (UI, copy, notifications end users see), has 3+ tasks, or has any task graded high/xhigh: publish a plan-review Artifact rendered FROM the plan file (load the `artifact-design` skill first). Decisions-first layout: TL;DR stats (tasks, effort grades, migrations, test counts), a small UI mockup when the change is user-facing, the locked decisions, one card per task (files, effort grade, tests), the full Sol audit trail (each round's verdict and what was fixed, unresolved notes flagged), and an on-approve pipeline strip. The plan `.md` stays canonical — the artifact is a rendering; regenerate it from the file after any plan change, never edit it independently.
   - If none of those hold (small, internal-only plan): no artifact. The gate message is a short chat summary — TL;DR stats, locked decisions, audit trail one-liners — plus the raw plan path.
   - Send the artifact URL (when one was published) plus the raw plan path, then ONE Approve/Revise question (AskUserQuestion). Invite task-anchored notes ("T2: …") via the Other option.
   - WAIT for explicit approval. This is the gate — do not start Stage 2 without it, and do not add further approval stops after it.

## Stage 2 — Workspace

Branch: `jjholmes927-<slug>[-TICKET]`. Resolve the workspace in this order:

1. **Already isolated?** If `[ -f "$(git rev-parse --git-dir)/gitdir" ]` (a linked worktree's git dir carries a `gitdir` file; a main checkout's does not — this holds from any subdirectory, unlike comparing `--git-dir` with `--git-common-dir`, which mixes absolute and relative paths), the current directory is a linked worktree — whoever launched this session (new-agent, Claude's background isolation, Kandev, or you by hand) already gave it its own workspace. Use the CURRENT worktree and create the branch in place. Never create a worktree inside it, and never key this decision on a runtime-specific variable such as `CLAUDE_JOB_DIR`: the same skill must behave identically under any launcher.
2. **Project provisioning next.** Else, if the repo ships `bin/create_worktree`, run `bin/create_worktree <branch>` and cd into the worktree it creates — it provisions env, database, credentials and agent memory fail-closed, which the generic skill cannot.
3. **Fallback.** Only when neither applies, invoke superpowers:using-git-worktrees.

Record the worktree path. Create `.e2e/` inside it and add `.e2e/` to the exclude file once: `EXCL=$(git -C <worktree> rev-parse --git-path info/exclude); mkdir -p "$(dirname "$EXCL")"; grep -qx '.e2e/' "$EXCL" 2>/dev/null || printf '\n.e2e/\n' >> "$EXCL"` (in a worktree `.git` is a file, so the literal `.git/info/exclude` path does not exist; `--git-path` resolves the real one, and the guard stops the line piling up on re-runs). This MUST happen before Stage 3 writes anything, else the no-diff check misreads `.e2e/` noise.

## Stage 3 — Implement each task (Sol)

For each plan task, in order:

1. Write the task prompt to `.e2e/task-N-prompt.md` containing: the plan task verbatim; relevant constraints from neighbouring tasks; the slice's acceptance checks, dependency decisions and runtime assumptions; "Read AGENTS.md (or CLAUDE.md if no AGENTS.md) in the repo root and follow its conventions"; "HARD RULE — NEVER add code comments: no explanatory, doc, or rationale comments, not even for non-obvious workarounds. Only exceptions: machine-required directives (rubocop:disable, eslint-disable, frozen_string_literal, shebangs) and updating an EXISTING comment your change makes factually stale. If something needs explaining, say it in your final message instead."; "Keep code readable: one statement per line, descriptive intermediate names and guard clauses where they clarify control flow. Never compress syntax, remove useful whitespace or omit tests to meet a PR size limit. Run the repository's formatter and linter for changed code."; "Run the project's tests for the code you changed and make them pass before finishing"; "Do not commit".
2. Run: `e2e-codex.sh run <worktree> <effort> .e2e/task-N-prompt.md` → capture thread id.
3. Append `task-N<TAB><thread-id><TAB><effort><TAB>implemented` to `.e2e/sessions.tsv`. Track every attempt's status by updating this file — never count retries from memory.
4. Failure policy (**implement: 1 retry then stop**): non-zero exit or no diff (`git -C <worktree> status --porcelain` empty) → retry ONCE with the error/`.e2e/last-message.txt` tail appended to the prompt, recording the retry in `.e2e/sessions.tsv`. Second failure → hard-stop per the Iron Laws.
   - Sandbox network is enabled via the wrapper, but on macOS codex's seatbelt has historically ignored it. If a failure looks like network/dependency-install denial rather than a code problem, do NOT burn the retry — surface it and suggest pre-installing deps in the worktree first.
   - If the wrapper prints no thread id, or the JSONL log is empty/malformed, treat it as a stage failure: inspect `.e2e/codex-*.jsonl` before retrying.
5. Checkpoint commit: `git -C <worktree> add -A && git -C <worktree> commit -m "wip: task N — <task title>"`. Record the sha.

## Stage 4 — Sol self-review

1. `e2e-codex.sh review <worktree> --commit <task-sha>` → capture output.
2. If it reports findings: write them to `.e2e/task-N-selffix.md` with "Fix these findings from your own review", then `e2e-codex.sh resume <worktree> <thread-id> <effort> .e2e/task-N-selffix.md`, and amend: `git -C <worktree> add -A && git -C <worktree> commit --amend --no-edit`. Amending rewrites the sha: re-capture it with `git -C <worktree> rev-parse HEAD` and use that fresh sha for all later reviews; never reuse a pre-amend sha. One self-review pass only.

## Stage 5 — Fable review + fix loop (**per-task Fable fix loop: 3 max**)

1. Dispatch a code-reviewer subagent (superpowers:requesting-code-review conventions) on `git -C <worktree> show <task-sha>` with the plan task as context, instructed to try to REFUTE its own findings before reporting — only findings that survive refutation are returned. Findings must be concrete: file, line, defect, why it matters.
2. Arbitrate and label each surviving finding by agreement: `[both]` (Sol's Stage 4 self-review also flagged it), `[claude-only]`, or `[codex-only]` (from Stage 4 but unfixed). Drop refuted findings and nits; keep real defects — `[both]` findings are highest-confidence, never drop them without re-verification.
3. If real defects remain: write them to `.e2e/task-N-fix-<loop>.md` as a fix brief, `e2e-codex.sh resume` with the task's effort, amend the checkpoint commit, then re-capture the sha with `git -C <worktree> rev-parse HEAD` and use that fresh sha for all later reviews (never reuse a pre-amend sha), and re-verify each finding yourself (read the diff — do not re-run the full review). Record each loop's status in `.e2e/sessions.tsv` — count loops from the file, never from memory.
4. After 3 loops, carry unresolved findings forward to Stage 7's PR-comment list, keeping their agreement labels.

## Stage 6 — Final branch review (Fable)

Whole-branch check against the approved plan: every task present, no plan drift, cross-task coherence (naming, duplication, dead code), readable control flow and complexity justified by the recorded dependency/runtime constraints. Check each proposed PR's release readiness without its successors; whole-stack success alone is insufficient. Real defects → one fix loop via `e2e-codex.sh resume` against the most relevant task session (effort `high`); still-unresolved → PR-comment list.

## Stage 7 — Ship

1. The plan file never enters the branch — docs/plans/ is a local working document; the PR carries implementation only. Invoke this plugin's ship command for each PR branch in dependency order. Ship formats and measures each PR against its actual base, enforcing both **at most 500 total added/deleted lines** and **an incrementally releasable, understandable unit of work**. A slice may depend on predecessors, never on successors for correctness. If a slice is too large, revise its boundaries into coherent, independently verified increments; checkpoint commits are only candidates for those boundaries. Never compress code, omit tests or publish a broken intermediate slice to meet the cap. Ship owns verification, commits, push, PR creation (What/Why) and CI watching for every resulting branch. Before ship commits leftovers, confirm `git status` shows no plan file staged (it should be gitignored; if not, leave it untracked).

   **Red flag — hand-rolling Stage 7 is a violation.** Running `git push` / `gh pr create` / a CI watch directly instead of invoking ship skips ship's verify gate, and transcript audits show this is the main path by which unverified changes reach PRs. Stacked PRs, multi-repo pushes, and "it's just a small branch" are not exemptions: invoke ship per branch. If ship genuinely cannot run (e.g. its skill is unavailable in this session), say so in the Stage 7 report and run /verify manually before any push.
2. Post each carried-forward finding as a PR comment: `gh pr comment <num> --body "..."` prefixed with `[e2e unresolved]`.
3. CI failures: ship owns the repair loop and its maximum of 3 rounds for the whole invocation. Hand repairs to `e2e-codex.sh resume` (effort `high`, most relevant task session), then return to ship for affected tests, re-verification, fingerprint/size checks, push and CI watch. Record each round in `.e2e/sessions.tsv`; do not add or reset a second CI retry budget here. The stricter two-consecutive-failures hard stop still applies.
4. Ticket and stream state — do this yourself, never ask the human whether to:
   - Only after the PR is up AND CI is green (or the only red checks are the non-blocking ones noted in the report): Linear ticket runs move the ticket to **In Review**: load the tool first (`ToolSearch(query="select:mcp__linear-server__save_issue")`), then `mcp__linear-server__save_issue(id: "<TICKET>", state: "In Review")`. Never move it to Done — Done follows the merge, not the PR. If the state name is rejected, report the error and leave the ticket where it is.
   - Then record the stream outcome: `fleet-status complete "<TICKET>: PR #<num> <url>"` (ad-hoc runs: describe the PR instead of a ticket). On any hard-stop — including the CI cap in step 3 — leave the ticket In Progress and record `fleet-status awaiting "<what is blocked and why>"` instead. Run it in your own shell, never via a subagent; if `fleet-status` is not on PATH, skip it and say so in the report.
5. Report: PR URL, tasks completed, fix-loop counts, unresolved findings, total codex sessions, ticket state.
