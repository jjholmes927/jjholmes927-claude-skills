---
name: dev-workflow-iterate
description: "Use when the user says /dev-workflow-iterate, asks for a workflow review, retro, or pulse ('what's working / missing / rotting', 'review my setup', 'is the tooling earning its keep'), when workflow friction has accumulated, or after a big process change beds in — monthly-ish for a light pulse, roughly quarterly for a deep review. Reviews the dev workflow itself with measured evidence and deletion-first output."
---

# Dev workflow iterate

Reviews the development workflow the way production gets reviewed: measured evidence, adversarial verification, changes sequenced deletion-first. Prior iterations live in the `workflow-control-plane-plan` memory — it carries the artifact URLs (readable via WebFetch) and the standing verdicts. Start there.

## When NOT to use

- A single tool question → answer it, with a live probe.
- One broken helper → superpowers:systematic-debugging.
- A one-off friction → a fix or a ticket, not a review.
- "Should I adopt tool X?" → a live probe plus the standing build-vs-adopt verdicts.

## Mode

**Default: light** (~30 minutes, no subagent fleet). Escalate to deep ONLY when the operator asks for it explicitly, or when ALL three hold: ≥ ~3 months since the last deep run, ≥ 3 distinct frictions queued, and a structural change in scope (new tooling era, team change, new machine). When in doubt, run light and say what a deep run would add. Deep costs several million tokens and hours.

## Iron laws (both modes)

1. **Prior art before proposals.** Read `/Users/joelholmes/engineering/second-brain/01-decisions/`, the `workflow-control-plane-plan` memory, and MEMORY.md's workflow rules BEFORE drafting anything. A recommendation contradicting a settled decision must name it and argue the reversal explicitly. (A prior run nearly shipped a "stream registry" the 2026-07-19 work-OS record had already ruled out.)
2. **Instruments before archaeology.** The helpers are dotfiles shell FUNCTIONS, not binaries — invoke via a login shell. The instrument set:
   - `bash -lc 'CLOSURE_REPOS="wearebeam/magicnotes wearebeam/infrastructure jjholmes927/jjholmes927-claude-skills wearebeam/beam-claude-skills jjholmes927/dotfiles" closure-sweep'` — the default repo list excludes the workflow's own repos; widen it for this run.
   - `bash -lc 'clone-status'` — note it fetches. It is the only lanes helper that is an instrument: `gmp-all` and `lane-sweep` MUTATE (stash, branch, checkout) and are never run as part of a review.
   - `gh pr list` stats: cadence, size and reviewability against the current ship rules, and the **unreviewed rate** = share of the last 60 merged PRs whose reviews are empty or bot-only (exclude Bugbot, the CI AI reviewer, and other bots explicitly; never trust `reviewDecision` alone).
   - Fleet snapshot: `claude agents --cwd ~/engineering --json` — read `state`/`waitingFor`, never `status`.
   - MEMORY.md Active-work aging against the `active-work-entry-contract` memory — its 7-day residue rule is light mode's cheapest deletion generator.
   - Current 5h/7d rate-limit headroom from the statusline payload — instantaneous only; no history exists anywhere.
   - The workflow-ledger (Honeycomb) is **not agent-queryable on this machine**: the MCP is scoped to team `beam`, the local ingest key 401s on queries. Recipes and the board URL are in `/Users/joelholmes/engineering/dotfiles/docs/agent-telemetry.md` §4 — ask the operator for a board read. Interpretation caveats: it records ATTEMPTS not outcomes, sees nothing from prompt-expansion commands, and fails silently — absence of events is never evidence of absence of usage.
   A broken or unreachable instrument is itself a top-priority **Rotting** finding — record it and continue.
3. **Live-verify every tool claim before recommending it.** Docs and web sources are hypotheses; run the command on this machine and tag findings LIVE / DOCS / WEB. Probes run in a scratch repo under the session scratchpad — never in a lane, and never via `gmp-all`, `lane-sweep`, or `git stash` anywhere during a review. (Docs-optimism produced two near-misses in a prior run: agent-view's real JSON schema, and `.worktreeinclude` vs `WORKTREE_OFFSET`.)
4. **No new surfaces.** The fix is fewer places to look, not another dashboard (01-decisions 2026-07-19: "a status dashboard — explicitly ruled out"). Any proposal adding a standing thing-to-check must displace something bigger.
5. **Deletion-first, consent-gated.** Phase 0 of any plan is scope cuts — but every cut is LISTED first (what, why, recoverable or not) and executed on the operator's go-ahead. Refusals that never relax: never remove a worktree with uncommitted changes or an unpushed branch (`git -C <worktree> status --porcelain` first); never touch a lane root hosting a live session; prefer `claude rm` (refuses dirty worktrees) over agent-view delete (destroys them); park WIP via `lane-sweep` rather than dropping it; dropped stashes are unrecoverable after gc. Secrets: an agent can scrub history, only a human can rotate — a scrub without the rotation is an OPEN INCIDENT, not a completed cut.
6. **Consent boundaries hold.** Team-facing changes (shared repos, review rotas, CI) are proposed, not shipped, unless explicitly asked. Never merge past a failing guard.

## Light mode

1. Run the instruments (law 2) and mark each of the previous iteration's items done / rotted / abandoned.
2. Answer three questions with evidence, one line per item:
   - **Working:** what earned its keep (usage evidence, not fondness)?
   - **Missing:** what friction did the operator feel — ask the operator for their own list; instruments miss feelings.
   - **Rotting:** what is now unused, drifted, or bypassed? Check plugin cache vs source, helper health, and overdue delete-whens.
3. Output: a short chat summary + up to five actions, at least one a deletion (consent-gated per law 5). Anything bigger becomes a memory entry satisfying the `active-work-entry-contract` (expected outcome, next action, delete-when).

## Deep mode

Budget preflight first: read the current 5h/7d headroom, state a token estimate, cap the panel at five lenses, pass `--effort` explicitly on every spawn, and run lenses serially if the 5h window is already hot.

Checklist (copy into the response and check off):

```
[ ] Evidence pack written to a scratchpad FILE (light-mode findings + fresh stats + the operator's open questions)
[ ] Research agents on OPEN questions only — cite prior verdicts, re-check only what could have changed
[ ] Draft recommendation written
[ ] Panel dispatched in ONE message, in parallel, all reading the pack file:
    build-steelman · pragmatist · attention-economics · claim-verifier (live probes, scratch repo only) · completeness critic
[ ] Blind cross-model opinion: joel-workflow:codex-collab ask at xhigh, evidence pack ONLY — never the draft
[ ] Reconcile panel vs Sol; unresolved forks get a decision rule ("do X for 4 weeks; if Y recurs, build Z"), never a compromise
[ ] Output: plan artifact per the standing plan-review rule (visual overview + Raw plan tab), 3-5 line chat summary,
    Phase 0 cuts consent-gated then executed, /Users/joelholmes/engineering/dotfiles/docs/operator-workflow.md updated,
    iteration memory written per the entry contract
```

## Common rationalizations

| Excuse | Reality |
|--------|---------|
| "I remember what we decided" | Read `01-decisions/`. A prior run nearly shipped a registry the 2026-07-19 record had ruled out. |
| "The docs are recent enough" | Docs are hypotheses. Tag LIVE/DOCS/WEB — docs-optimism shipped two near-misses in a prior run. |
| "This addition is small" | Law 4: it must displace something bigger. |
| "Nothing obvious to delete" | The attention lens failed — re-run it. |
| "The cut is obviously safe, just do it" | Law 5: list, confirm, then cut. Uncommitted worktrees are unrecoverable. |

## Red Flags — STOP

- Recommending a tool from docs or star counts without a live probe.
- A plan whose Phase 1 is a build — a prior run's biggest find was a wiring bug (`/e2e` bypassing `bin/create_worktree`), not a missing system.
- The review producing only additions.
- Skipping the operator's own "what felt bad" list.

All of these mean: stop drafting, return to the instruments, and re-derive the recommendation from evidence.
