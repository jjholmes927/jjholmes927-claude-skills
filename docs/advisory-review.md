# Advisory review

The shared E2E and ship workflows use the same collector and decision commands.
Run these from the project worktree, using the script in the selected plugin:

```sh
python3 -B skills/e2e/scripts/advisory_review.py scan <base> --harness codex --workflow ship
python3 -B skills/e2e/scripts/advisory_review.py decide <id> kept 'The sequence belongs together'
python3 -B skills/e2e/scripts/advisory_review.py decide <id> dismissed 'Generated declaration covered by the project policy'
python3 -B skills/e2e/scripts/advisory_review.py decide <id> fixed 'Removed the mixed responsibility'
python3 -B skills/e2e/scripts/advisory_review.py check
```

Use the actual harness, and supply task/session IDs when available. A raw size or
complexity threshold is a review signal. The decision requires a reason; a fix
requires a fresh successful scan. Changing lint configuration, baselines or adding
inline suppression does not establish a verified fix. After repairs, rescan and
renew decisions for the new tree. Committing identical content keeps decisions
valid; changing content invalidates them.

Reports and decisions stay under `.e2e/`, excluded from Git. The collector uses
configured RuboCop, ESLint and jscpd, with their existing exclusions and baselines.
It checks changed files and enclosing diagnostic ranges; duplication scans the
configured project and selects clones overlapping changed code. Exit 0 allows
advisories, 1 preserves blocking lint failures, and 2 means incomplete evidence.

Honeycomb receives `quality_advisory_scan`, `quality_advisory_flagged` and
`quality_advisory_reviewed` events through the existing workflow ledger. Gate
checks emit `quality_advisory_gate` with ready, unreviewed, stale, blocking or
incomplete status; current complete reports include their unreviewed count. Each has
the run, revision/tree, canonical repository and actual harness; findings include
tool/rule and finding ID, and decisions include outcome and verified-fix status.
Source snippets and review reasons stay local. Available task/session and trace
context are forwarded; missing trace context is not invented. Delivery failures
retain the local ledger and are reported. `E2E_LEDGER=off` disables network export.

Count flag events for repeated occurrences, distinct finding IDs for unique
findings, and distinct review IDs for decisions. Compare outcomes by rule and
harness. A justified keep is a completed review; reviewed and fixed are different
measures. These are workflow events, not proof of cross-harness model quality.

The [Agent quality review board](https://ui.eu1.honeycomb.io/agent-traces/environments/beam-work/board/rh-CdrBofCYQ)
shows occurrences, unique findings, decisions, verified fixes and scan/review gaps.
Its panels exclude `--workflow verification` fixture runs. Collector revisions
are recorded so changes to diagnostic identity can be distinguished from growth.
