---
name: e2e
description: "Full pipeline: Fable plans, you approve once, Sol 5.6 (codex) implements each task headlessly with per-task reasoning effort, Sol self-reviews, Fable arbitrates and drives fix loops, then ship to PR with CI watch. Use when the user says /e2e, 'take this end to end', 'run the e2e flow', or gives a ticket/prompt to fully implement hands-off."
---

# e2e — Fable plans, Sol implements, both review

Wrapper script: `${CLAUDE_PLUGIN_ROOT}/skills/e2e/scripts/e2e-codex.sh`
(`run <workdir> <effort> <prompt-file>` → prints codex thread id; `resume <workdir> <thread-id> <effort> <prompt-file>`; `review <workdir> [--commit <sha>|--base <branch>|--uncommitted]`)

## Arguments

- `/e2e INT-123` — Linear ticket: first invoke joel-workflow pick-up-linear-ticket for context and status moves.
- `/e2e "<task description>"` — ad-hoc prompt.
- `--dry-run` anywhere in the args: run stages 1–2 normally, then print every wrapper command you would run instead of running it, and stop before ship.

## Hard rules

- Fable (you) NEVER writes production code in this flow. All code — implementation, review fixes, CI fixes — goes through the wrapper to Sol.
- The plan gate is the ONLY human gate. Never add extra confirmation stops after plan approval; never skip the plan gate.
- Any stage failing twice: STOP. Report worktree path, task, thread ids from `.e2e/sessions.tsv`, and the last error. Never delete the worktree on failure.

## Stage 1 — Plan (Fable)

1. If the argument is a Linear ticket id, invoke the pick-up-linear-ticket command from this plugin first.
2. Invoke superpowers:brainstorming (keep it brief for small, well-specified tasks), then superpowers:writing-plans.
3. The plan MUST give each task: exact file paths, test expectations, and an **effort grade** — `low` (mechanical/boilerplate), `medium` (routine feature code), `high` (cross-cutting logic), `xhigh` (algorithmic/subtle). Grade by task complexity, not project importance.
4. Present the plan and WAIT for explicit user approval. This is the gate.

## Stage 2 — Workspace

Invoke superpowers:using-git-worktrees. Branch: `jjholmes927-<slug>[-TICKET]`. Record the worktree path. Create `.e2e/` inside it and add `.e2e/` to `.git/info/exclude` in the worktree.

## Stage 3 — Implement each task (Sol)

For each plan task, in order:

1. Write the task prompt to `.e2e/task-N-prompt.md` containing: the plan task verbatim; relevant constraints from neighbouring tasks; "Read AGENTS.md (or CLAUDE.md if no AGENTS.md) in the repo root and follow its conventions"; "Run the project's tests for the code you changed and make them pass before finishing"; "Do not commit".
2. Run: `e2e-codex.sh run <worktree> <effort> .e2e/task-N-prompt.md` → capture thread id.
3. Append `task-N<TAB><thread-id><TAB><effort><TAB>implemented` to `.e2e/sessions.tsv`.
4. Failure policy: non-zero exit or no diff (`git -C <worktree> status --porcelain` empty) → retry ONCE with the error/`.e2e/last-message.txt` tail appended to the prompt. Second failure → hard-stop per the rules above.
5. Checkpoint commit: `git -C <worktree> add -A && git -C <worktree> commit -m "wip: task N — <task title>"`. Record the sha.

## Stage 4 — Sol self-review

1. `e2e-codex.sh review <worktree> --commit <task-sha>` → capture output.
2. If it reports findings: write them to `.e2e/task-N-selffix.md` with "Fix these findings from your own review", then `e2e-codex.sh resume <worktree> <thread-id> <effort> .e2e/task-N-selffix.md`, and amend: `git -C <worktree> add -A && git -C <worktree> commit --amend --no-edit`. One self-review pass only.

## Stage 5 — Fable review + fix loop (max 2 loops per task)

1. Dispatch a code-reviewer subagent (superpowers:requesting-code-review conventions) on `git -C <worktree> show <task-sha>` with the plan task as context. Findings must be concrete: file, line, defect, why it matters.
2. Arbitrate: discard nits and false positives yourself; keep real defects.
3. If real defects remain: write them to `.e2e/task-N-fix-<loop>.md` as a fix brief, `e2e-codex.sh resume` with the task's effort, amend the checkpoint commit, and re-verify each finding yourself (read the diff — do not re-run the full review).
4. After 2 loops, carry unresolved findings forward to Stage 7's PR-comment list.

## Stage 6 — Final branch review (Fable)

Whole-branch check against the approved plan: every task present, no plan drift, cross-task coherence (naming, duplication, dead code). Real defects → one fix loop via `e2e-codex.sh resume` against the most relevant task session (effort `high`); still-unresolved → PR-comment list.

## Stage 7 — Ship

1. Invoke the ship command from this plugin inside the worktree. Let it format, commit leftovers, push, open the PR (What/Why), and watch CI.
2. Post each carried-forward finding as a PR comment: `gh pr comment <num> --body "..."` prefixed with `[e2e unresolved]`.
3. CI failures: hand the failure log to `e2e-codex.sh resume` (effort `high`, most relevant task session), push, re-watch. Max 2 rounds, then hard-stop and report.
4. Report: PR URL, tasks completed, fix-loop counts, unresolved findings, total codex sessions.
