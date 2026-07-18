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
- **Running a loop past its cap** (implement: 1 retry; Fable fix loop: 3; CI fix: 2; plan audit: 2) → STOP, hard-stop and carry findings to PR comments.
- **Deleting/recreating the worktree after failure** → STOP, leave it and report its path.
- **Shipping with unresolved findings** → STOP, post each as a `[e2e unresolved]` PR comment first.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| It's a one-line fix, faster myself | All code goes through Sol — no line-count threshold |
| Sol failed twice, I'll finish it | Two failures = hard-stop and report, not takeover |
| I'll just add one more check-in with the user | The plan gate is the ONLY gate |
| Findings are minor, ship clean | Every unresolved finding becomes a PR comment |

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
4. Sol plan audit (cross-model, before the human sees the plan): write the plan plus "Audit this plan for correctness, security, and completeness against the repo. Verdict: READY, or REVISE with concrete issues." to a temp file; run `e2e-codex.sh audit <repo-root> <file>` (read-only sandbox — safe on the main checkout). On REVISE, fix the issues and re-audit. Max 2 audit rounds; if still REVISE, present the plan with the unresolved audit notes attached.
5. Present the plan (with Sol's verdict) and WAIT for explicit user approval. This is the gate.

## Stage 2 — Workspace

Invoke superpowers:using-git-worktrees. Branch: `jjholmes927-<slug>[-TICKET]`. Record the worktree path. Create `.e2e/` inside it and append `.e2e/` to the file at `git -C <worktree> rev-parse --git-path info/exclude` (in a worktree `.git` is a file, so the literal `.git/info/exclude` path does not exist; this resolves the real exclude file). This MUST happen before Stage 3 writes anything, else the no-diff check misreads `.e2e/` noise.

## Stage 3 — Implement each task (Sol)

For each plan task, in order:

1. Write the task prompt to `.e2e/task-N-prompt.md` containing: the plan task verbatim; relevant constraints from neighbouring tasks; "Read AGENTS.md (or CLAUDE.md if no AGENTS.md) in the repo root and follow its conventions"; "Run the project's tests for the code you changed and make them pass before finishing"; "Do not commit".
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

Whole-branch check against the approved plan: every task present, no plan drift, cross-task coherence (naming, duplication, dead code). Real defects → one fix loop via `e2e-codex.sh resume` against the most relevant task session (effort `high`); still-unresolved → PR-comment list.

## Stage 7 — Ship

1. Invoke the ship command from this plugin inside the worktree. Let it format, commit leftovers, push, open the PR (What/Why), and watch CI.
2. Post each carried-forward finding as a PR comment: `gh pr comment <num> --body "..."` prefixed with `[e2e unresolved]`.
3. CI failures (**CI fix: 2 max**): hand the failure log to `e2e-codex.sh resume` (effort `high`, most relevant task session), push, re-watch. Record each round in `.e2e/sessions.tsv` and count from the file, never from memory. After 2 rounds, hard-stop and report.
4. Report: PR URL, tasks completed, fix-loop counts, unresolved findings, total codex sessions.
