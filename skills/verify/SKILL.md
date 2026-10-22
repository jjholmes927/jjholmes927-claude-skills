---
name: verify
description: Evidence-based verification of ANY change — UI or not — before claiming it works, finishing a task, or shipping. Decides what evidence would prove the behaviour, gathers it from the running system (browser via verify-ui, DB read-backs, real invocations), and reports verified / partial / not-verifiable with the evidence shown. Invoke after implementing anything, whenever the user asks "did you test it?", and always as ship's verification stage.
---

# Verify

Claims about behaviour require evidence from a running system. Green tests, clean types, and passing CI are inputs — never the conclusion.

**Origin lesson:** a telemetry PR once sat with 44 CI checks green, 950+ unit tests passing, and review bots satisfied — while its core event listener had never executed anywhere, and its headline metadata field was structurally incapable of being false in production. Everything was green around a feature that could not do its job. The gap was only caught because a human asked "did you actually test it?". This command exists so nobody has to ask.

## Step 1: Write the promise before choosing a tool

State in one or two lines the observable behaviour the change promises — what a skeptic who cannot read the code would need to see. If you catch yourself listing test names or file paths, start again. The promise is about the system, not the diff.

## Step 2: Route by change type

| Change | Evidence bar | How |
|---|---|---|
| UI / interaction / visual | Screenshot or snapshot of the real page doing the thing | Invoke **verify-ui** — it owns target resolution, auth, and the agent-browser playbook |

**UI routing is decided by file paths, not judgement.** If the diff touches any of:
`app/javascript/`, `app/views/`, `app/components/`, `app/avo/`, `*.tsx|*.jsx|*.css|*.scss`, or locale/translation files consumed by the frontend (`config/locales/`, `*-translations.json`) — the change IS a UI change and routes to **verify-ui**, even when a server-side read-back would be easier. Model-level facts ("the key resolves", "the option list is correct") may supplement but never substitute for the rendered page. If the browser arm is genuinely impossible right now, the report carries an explicit 🔴 for the UI promise — never a server-side ✅ standing in for it, and never silence.
| Telemetry / audit / analytics | The emitted row or event **read back from storage**, with the payload fields the change promises | Drive the path in the running app, then query it back (console/runner, SQL, log tail). Row-exists is not enough — assert the fields |
| API / service behaviour | Real request → response, AND the side effect | curl or console/runner against the dev server, then observe the effect |
| Background job | The job executed and its outcome record observed | Enqueue and perform inline, read the result record |
| Event listener / callback / subscription | The handler demonstrably fired via the **real trigger** at least once | Dispatch the actual event; a test may stand in only if it dispatches the real event rather than calling the handler directly |
| Config / flags / env | The effective value read from a booted process | Console/runner — not the file |
| DB migration | Migration run, schema + a real row inspected | Migrate dev DB, query it |
| CLI / script | Run on a real sample, output shown | Run it |
| Pure refactor / types-only / docs | Tests + type-check (or rendering, for docs) can suffice — but the report must say that explicitly | State "refactor-only: behaviour covered by existing tests" as the evidence line |

## Step 3: Rules of evidence

- **Signals are not proofs.** A success signal emitted by the code under test proves scheduling, not outcome — a "playback started" metric once fired on every turn while the room stayed silent. Prefer observing the effect somewhere the code doesn't control: the DB row, the rendered pixels, the external system's log.
- **Read-back rule.** Anything that writes must be read back through a different interface than the writer used.
- **Vacuous-test check.** For each key assertion ask: can production actually produce this input? A test feeding values the runtime never emits proves nothing — tests once passed sink ids a plain AudioContext can never report, masking a field that was constant in production.
- **Exercise the wiring, not just the units.** A unit test that sends an event by hand proves the handler's logic, not that anything subscribes to it. At least one test or manual run must go through the real trigger.
- **A/B unexplained failures against a clean baseline.** `git stash -u` → run → `git stash pop`. Failing on clean main too means it isn't yours. If the suite flakes under parallel load, rerun sequentially (`--no-file-parallelism` or equivalent) before blaming the change.

## Step 4: Repair the environment — never downgrade the verification

Missing tooling is a task, not an excuse. Deps out of sync → install them. DB behind → migrate. Dev server down → start it (background it, then poll). A broken toolchain is not a reason to ship unverified.

When the UI path is needed, ensure agent-browser exists **and is current**:

```bash
which agent-browser || (npm i -g agent-browser && agent-browser install)
INSTALLED=$(npm ls -g agent-browser --parseable --long 2>/dev/null | sed -n 's/.*agent-browser@//p')
LATEST=$(npm view agent-browser version 2>/dev/null)
[ -n "$LATEST" ] && [ "$LATEST" != "$INSTALLED" ] && npm i -g agent-browser@latest && agent-browser install
```

The freshness check is timeboxed and non-fatal: if the registry is unreachable, proceed on the installed version and say so. If installation itself fails, that is a 🔴 — report it; do not quietly fall back to "tests pass".

## Step 5: Report with the evidence shown

Exactly three statuses. Every promise from Step 1 gets one.

- ✅ **Verified** — the command/action run, the observed output (pasted, trimmed), and one line on what it proves.
- 🟡 **Partially verified** — what is proven, what is not, why, and where the remainder gets proven (staging, post-deploy query, hardware test).
- 🔴 **Not verifiable here** — the concrete reason (needs real hardware, prod-only data, missing credentials) and the post-ship verification plan.

A verification that was skipped without being declared is a failure of this command — silence is the one prohibited outcome.

## Step 6: Bind the verdict to the exact code that was verified

A verdict is only true for the tree it was run against. Record it against a fingerprint of the working tree (tracked + uncommitted + untracked, ignored files excluded) so ship can refuse to push anything that changed afterwards. Committing the verified content does not change the fingerprint; editing a line does.

```bash
TOP=$(git rev-parse --show-toplevel)
EXCL=$(git rev-parse --git-path info/exclude); mkdir -p "$(dirname "$EXCL")"
grep -qx '.verify/' "$EXCL" 2>/dev/null || printf '\n.verify/\n' >> "$EXCL"
IDX=$(mktemp); cp "$(git rev-parse --git-path index)" "$IDX" 2>/dev/null || rm -f "$IDX"
GIT_INDEX_FILE="$IDX" git -C "$TOP" add -A . >/dev/null 2>&1
TREE=$(GIT_INDEX_FILE="$IDX" git -C "$TOP" write-tree); rm -f "$IDX"
mkdir -p "$TOP/.verify"
```

Write `$TOP/.verify/$TREE.json` when the overall verdict is ✅ or 🟡:

```json
{"tree": "<TREE>", "head": "<output of git rev-parse HEAD, informational only — ship matches on tree>", "at": "<ISO-8601 UTC>", "verdict": "verified|partial",
 "arms": ["unit", "ui", "read-back"], "promises": [{"promise": "...", "status": "verified", "evidence": "<command → observed output, one line>"}]}
```

Rules: a 🔴 verdict writes nothing (ship's loud 🔴 path stays the only way past). The `.verify/` exclude must be in place before the fingerprint is computed, or the record perturbs its own hash. The record is evidence, not the verdict — the pasted ✅/🟡/🔴 block in chat is still required.

## Anti-patterns

- "Tests pass, therefore it works"
- Accepting the happy signal the code itself emits as proof of outcome
- Quietly skipping because a tool is missing or a server is down
- Demonstrating the code (diff screenshots, log statements) instead of the behaviour
- Claiming UI correctness without a screenshot or snapshot — verify-ui's iron rule holds here too
- Declaring 🔴 for something that was verifiable with ten minutes of environment repair

## Arguments

$ARGUMENTS — Optional: a hint of what changed (ticket, PR ref, or free text). Empty → derive the promises from the current diff and recent commits.

## Checklist

- [ ] Promise written before any tool chosen
- [ ] Evidence gathered per change type; UI routed through verify-ui
- [ ] Writes read back through a different interface than the writer
- [ ] Real trigger exercised at least once — no hand-called handlers standing in for wiring
- [ ] Environment repaired (tools installed/updated, server started) rather than verification downgraded
- [ ] Report shows evidence per promise, or declares 🟡/🔴 with reason and follow-up plan — never silence
- [ ] ✅/🟡 verdict recorded in `.verify/<tree>.json` against the working-tree fingerprint (Step 6)
