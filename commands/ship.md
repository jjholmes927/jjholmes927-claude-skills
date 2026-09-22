---
description: End-to-end PR workflow — format, commit, verify behaviour with evidence (always, via /verify), push, open the PR, watch CI fail-fast, then consolidate Bugbot and AI-review feedback. Use when work is ready to become a pull request, or the user asks to ship it.
---

# Ship

End-to-end workflow: format, branch, commit, verify with evidence, push, PR, fail-fast CI watch, consolidate review feedback.

## Workflow

```
Preflight → Format → Stage → Branch (if on main) → Commit → Verify (ALWAYS, evidence-based)
   → Simplify → Push → Create PR → Watch CI (required, fail-fast)
                                            │
                                    ┌───────┴───────┐
                                 CI Green      CI Failed
                                    │               │
                         Consolidate reviews   Fix fast + push
                         (Bugbot + AI review)   └──→ Watch CI
                         fix valid → push
                                    │
                                  Done
```

## Step 0: Preflight

When `command -v workflow-doctor` succeeds, run `workflow-doctor` once and report any warnings with their refresh commands. It checks local source/adapter drift without updating anything. Warnings are informational, introduce no approval gate and do not waive verification requirements. If unavailable, report that drift was not checked and continue the normal preflight; dotfiles documents installation.

Before anything, verify prerequisites:

```bash
git rev-parse --git-dir        # We're in a git repo
git status --porcelain         # Uncommitted work, if any
gh auth status                 # GitHub CLI is authenticated
```

Resolve the PR base (the existing PR's base, the stack parent, or the repository's actual default branch) as `$BASE` and verify the ref exists. Do not assume the default is `main`; inspect repository metadata. Inspect both `git diff "$BASE"...HEAD` and uncommitted work. A clean working tree with committed, unpublished changes must continue through verification and publication. Stop for no work only when both are empty; do not create an empty commit. If the base is unavailable, resolve it before deciding there is no work.

Record the corresponding GitHub base branch name as `$PR_BASE_BRANCH` (for example, `main` for `origin/main`). For a stack, publish predecessors first and use the immediate parent branch as the next PR's base; creating every PR against the default branch would measure and publish different diffs.

Check for an existing PR on the current branch and capture its number for later steps:
```bash
PR_NUMBER=$(gh pr view --json number -q .number 2>/dev/null)
```
If `$PR_NUMBER` is set, a PR already exists — skip PR creation in Step 6 (just push) and reuse `$PR_NUMBER` in Steps 7–8. Otherwise Step 6 creates the PR; use that number from then on.

## Step 1: Format

Detect changed file types and run the repository's configured formatters and linters before committing, verification and size measurement:

```bash
git diff "$BASE"...HEAD --name-only
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Only run tools for file types that actually changed. Follow the repository guide and configured package manager/scripts; common commands are:
- Ruby files (`.rb`) → `diffocop -A` (if available, else the configured RuboCop command)
- JS/TS/CSS files → `pnpm run format:fix && pnpm run lint:fix` when those scripts exist; otherwise use the repository's configured equivalents

Do not assume every Node repository uses pnpm or add a competing formatter. If no formatter/linter is configured, report that and check readability directly. Formatting does not replace review of control flow and design.

## Step 2: Stage + Branch

Stage all changes (formatting + implementation):
```bash
git add <specific files>   # Prefer specific files over git add -A
```

If on `main`, create a branch **before** committing:
```bash
git checkout -b jjholmes927-<descriptive-name>-<TICKET-ID>
```

## Step 3: Commit

Commit only when there are intended uncommitted changes. Already committed work proceeds directly to verification.

Use conventional commit prefixes:

| Prefix | Use |
|--------|-----|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `refactor:` | Code restructuring |
| `chore:` | Deps, config, misc |
| `perf:` | Performance |
| `test:` | Tests only |
| `ci:` | CI changes |
| `docs:` | Documentation |
| `style:` | Formatting only |
| `build:` | Build system, deps |
| `ops:` | Infrastructure, deployment |
| `revert:` | Reverts a previous commit |

Format: `prefix: Imperative description`

**Rules:**
- NEVER add Co-Authored-By or Claude attribution
- Use imperative mood ("Add feature" not "Added feature")
- Keep subject line concise
- Add ticket reference in body if relevant (e.g., `INT-107`)
- For multi-line messages, write the message to a temp file and use `git commit -F <file>`, or use a **quoted** heredoc delimiter (`<<'EOF'`) — an unquoted heredoc lets backticks / `$(...)` in the body get shell-evaluated and mangle the message

## Step 4: Verify (ALWAYS — evidence-based, never silently skipped)

Every ship verifies behaviour before push — UI or not. Invoke **/verify**: it writes the promise, picks the evidence per change type (UI → verify-ui, telemetry → read-back, API/job → real invocation), and reports ✅/🟡/🔴 with the evidence shown. "Tests pass" is not verification.

1. **Tooling preflight — repair, don't skip.** If the diff touches UI paths:
   ```bash
   git diff "$BASE"...HEAD --name-only | grep -E '\.(tsx?|jsx?|css|scss)$|^app/javascript/|^app/views/|^app/components/'
   ```
   and agent-browser is missing or stale, **install/update it now** — do not skip UI verification because the tool is absent:
   ```bash
   which agent-browser || (npm i -g agent-browser && agent-browser install)
   ```
   (/verify's Step 4 has the freshness check — run it.)
2. **Server preflight.** Verify against THIS clone's local dev server (parallel-dev setup), not staging:
   ```bash
   TARGET_URL=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve-dev-url.py") || exit 1
   curl -s -o /dev/null -w "%{http_code}" "$TARGET_URL"
   ```
   Not up → start it in the **background** (never run `bin/dev` in the foreground — it blocks) and poll until ready:
   ```bash
   DEV_LOG=$(mktemp -t ship-dev)
   bin/dev >"$DEV_LOG" 2>&1 &
   for i in $(seq 1 30); do curl -sf -o /dev/null "$TARGET_URL" && break; sleep 2; done
   ```
   A down server is an environment to fix, not a reason to skip. If it genuinely won't boot, that becomes a declared 🔴, never a quiet omission.
   Read the repository's runtime guide first. The resolver uses `bin/dev-info`'s `APP_URL` when available, then checkout `.env` and `.env.local` values; it never guesses port 3000 or sources environment files. If the project uses another contract, follow it explicitly and record the checkout and target URL. Resolve a missing or failing helper before checking a different server. Server checks are needed only for promises that require that server.
3. **Run /verify scoped to the diff** — exercise only the paths that changed, against `$TARGET_URL` for the UI arm.
4. **Real breakage → fix, re-stage, commit, re-verify.** Verification is gating pre-push.
5. **Gate on the verdict:**
   - ✅ / 🟡 → continue. The evidence lines go in the ship summary.
   - 🔴 because verification was possible but not done → **STOP. Do not push.** Go do it.
   - 🔴 genuinely not verifiable here (hardware, prod-only data) → push is allowed, but **SHOUT**: the ship summary MUST lead with `🔴 NOT VERIFIED LOCALLY — <reason>`, and the post-ship verification plan goes at the end of the PR body. Never bury it.
6. **The verdict block is a push precondition.** The ship summary MUST contain the verify verdict line(s) — `✅/🟡/🔴` per promise, each with its evidence (command + observed output) — pasted verbatim, not paraphrased as "verified". Invoking /verify is not the gate; the emitted verdict is. A verify launch that produced no verdict block counts as a skip: go back and produce it before push.

**Pre-declared verification** (evidence gathered before ship was invoked, cited via ship's args): acceptable only when the args quote the actual evidence — the command and its observed output. An unquoted assertion ("already verified", "no local auth so CI will cover it") does not stand; run /verify anyway. Untested premises about the environment (e.g. "auth is broken locally") must be re-tested at ship time before they excuse anything.

## Step 5: Simplify

Before pushing, invoke the available `simplify` skill to review the full branch diff for code reuse, quality and efficiency. If the harness has no such skill, perform those same three checks with its native review tools. Delegate only when the session authorizes it; otherwise review sequentially. If a parent workflow assigns edits to an implementer, return fixes to that implementer.

Check structural readability: one statement per line, descriptive intermediate names and guard clauses where they clarify control flow. Reject dense expressions or missing tests introduced to satisfy a size limit. Preserve the repository's comment convention; do not add explanatory comments as a substitute for clear structure. Check bespoke protocol and state-management machinery against the recorded dependency and runtime constraints.

If simplify made changes, stage and create a new commit before proceeding:
```bash
git add <changed files>
git commit  # New commit with fixes from simplify
```

If no issues were found, proceed directly to push.

If `/simplify` changed any files, re-run Step 4's verification for the paths it touched before pushing — those edits weren't covered by the earlier pass.

## Step 6: Push + Create PR

**Fingerprint gate (runs immediately before the push, after every commit is made).** /verify Step 6 recorded its verdict against a fingerprint of the exact working tree. The gate assumes everything verified is committed: run `git status --porcelain` first and, if it is non-empty, commit the remainder (or remove stray files) and re-run /verify — a dirty tree makes the record describe code the push does not carry. Then recompute the fingerprint and require a matching record:

```bash
TOP=$(git rev-parse --show-toplevel)
EXCL=$(git rev-parse --git-path info/exclude); mkdir -p "$(dirname "$EXCL")"
grep -qx '.verify/' "$EXCL" 2>/dev/null || printf '\n.verify/\n' >> "$EXCL"
IDX=$(mktemp); cp "$(git rev-parse --git-path index)" "$IDX" 2>/dev/null || rm -f "$IDX"
GIT_INDEX_FILE="$IDX" git -C "$TOP" add -A . >/dev/null 2>&1
TREE=$(GIT_INDEX_FILE="$IDX" git -C "$TOP" write-tree); rm -f "$IDX"
[ -f "$TOP/.verify/$TREE.json" ] && echo "verify record found for $TREE" || echo "NO VERIFY RECORD for $TREE"
```

- No record and no verify verdict block in this session → /verify never ran. Back to Step 4. Absence of a record is never evidence of "not verifiable".
- Record found → continue to the PR readiness and size gates below.
- No record and the Step 4 verdict was ✅/🟡 → something changed after verification (a simplify edit, a formatter, a late fix). **Do not push.** Re-run /verify on the current tree, then re-check.
- No record because Step 4 ended in a declared 🔴 not-verifiable → the existing 🔴 SHOUT path applies; push is allowed only with the `🔴 NOT VERIFIED LOCALLY` lead line.
- A `.verify/` directory is local evidence (git-excluded). Never commit it, never delete or hand-write a record to get past the gate — that is forging evidence.

**PR readiness gate (every PR, including each PR in a stack).** Each PR must be an **incrementally releasable, understandable unit of work**: one coherent purpose, enough context to review it, its own acceptance evidence, and a state safe to merge and release after its predecessors even if no successor ever lands. A tested foundation or safely inactive integration can qualify. A PR requiring the next PR to restore working behaviour cannot. Verify each branch at its own tip; tests run only on the final stack do not prove earlier slices. State the slice's purpose, predecessor and release behaviour in the PR description using the existing format.

**Size gate (runs before the push, on the exact diff the PR will show).** Every PR must also contain **at most 500 total added/deleted lines — app code, tests, docs and non-lockfile generated text all count (package-manager lockfiles and schema dumps are excluded from the size gate)**. This is a packaging/stacking rule, never a code-compression rule: do not minify code, combine statements onto one line, remove useful whitespace or omit tests to pass. Measure the formatted, committed code against `$BASE` resolved in Step 0: the actual stack parent for a stacked PR. Do not reset that base to `origin/main`.

```bash
set -o pipefail
: "${BASE:?Resolve the PR base in Step 0}"
git diff --numstat "$BASE"...HEAD | awk -F '\t' '
  $3 ~ /(^|\/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|Gemfile\.lock|composer\.lock|Cargo\.lock|db\/schema\.rb)$/ { next }
  $3 ~ /(^|\/)(spec|test|tests|__tests__)\/|\.(test|spec)\./ { t += $1 + $2; next }
  $3 ~ /^docs\// { d += $1 + $2; next }
  { a += $1 + $2 }
  END { total = a + t + d; printf "app=%d tests=%d docs=%d total=%d\n", a, t, d, total; exit (total > 500) }
'
```

- total ≤ 500 AND the PR readiness gate passes → continue; paste the measurement and the slice's release-readiness evidence in the ship summary. The app/tests/docs split is reporting only; tests do not receive a separate allowance.
- total > 500 OR the slice is not independently releasable/understandable → **do not push or create the PR.** Propose coherent boundaries, then restructure the commits and ship each resulting branch in dependency order with its own formatting, /verify, fingerprint, readiness and size checks. Splitting at an arbitrary commit boundary is insufficient. If no valid split fits the cap, report the constraint and stop rather than silently exempting files or compromising correctness.
- A failed measurement or unresolved base is not a pass. Re-check both gates after fixes or stack rebases; changed content invalidates verification evidence. Binary changes have no numeric line count in numstat and still require explicit review and verification.

```bash
git push -u origin <branch-name>
```

If no PR exists yet, create one with `gh pr create`.

### Writing the body

Invoke the **`writing-pr-descriptions`** skill and follow it exactly — it owns the format (What / Why), the 3-bullet / 2–3-sentence section caps, and the hard rules (one idea per sentence, outcome not inventory, stack etiquette, no Fixes footer, no attribution).

**If Step 4 produced UI verification screenshots, they go in the PR body — gating.** Follow the repository's attachment policy and verify-ui's evidence guidance; include the measurement line under each image. When upload requires a human action, preserve the files and report that pending action. Do not commit screenshots when the repository forbids it.

### Creating the PR

Write the body to a temp file (Write tool or an editor) and pass it with `--body-file` — never inline the body in `--body "..."` or a heredoc, because backticks in the body get shell-evaluated and mangle it. Capture the new PR's number so Steps 7–8 can use it:

```bash
gh pr create --base "$PR_BASE_BRANCH" --title "feat: Title here [TICKET-ID]" --body-file /tmp/pr-body.md
PR_NUMBER=$(gh pr view --json number -q .number)
```

## Step 7: Watch CI (fail fast)

Watch all checks and bail the instant one fails. Do NOT use `--required`: none of our repos configure branch-protection required checks, so `--required` returns "no required checks reported" and the watch silently no-ops — this failed in every repo it was tried in. Wait for checks to register first, or `--watch` hits a "no checks yet" race right after PR creation, returns non-zero, and falsely trips the fix loop:

```bash
for i in $(seq 1 12); do
  n=$(gh pr checks <PR_NUMBER> --json name --jq 'length' 2>/dev/null || echo 0)
  [ "${n:-0}" -gt 0 ] && break
  sleep 5
done
gh pr checks <PR_NUMBER> --watch --fail-fast --interval 20
```

If the repo has no CI at all (zero checks after the registration poll), say so in the ship summary and move on — don't invent a gate.

- **Exit 0** → all checks passed → go to Step 8.
- **Non-zero** → a check failed and `--fail-fast` bailed immediately. First check whether the failure is a slow non-blocking check (branch deploy, Chromatic, a review bot still running) — if so, note it and keep watching the rest. For real CI failures, fix now:
  1. Identify the failed check(s): `gh pr checks <PR_NUMBER>` (look for `fail`/`X`).
  2. Fetch the errors:
     - RSpec → use `.claude/skills/fetching-ci-errors/fetch_ci_errors` if present.
     - ESLint / TypeScript / Prettier / other → find the failed run, then view its log: `gh pr checks <PR_NUMBER> --json name,bucket,link --jq '.[]|select(.bucket=="fail").link'`, then `gh run view <run-id> --log-failed` (run-id from that link).
  3. Fix locally, run affected tests, commit (new commit, NOT amend), re-run Step 4 for changed behaviour and Step 6's fingerprint/size gates, then push.
  4. Re-run the watch. **Max 3 fix rounds**, then stop and report.

Ship owns this CI repair budget for the entire invocation, including returns from review feedback. Record attempts in the task handoff (or `.e2e/sessions.tsv` when E2E owns the task), preserve the count on resume, and do not restart it in the caller. A parent workflow's stricter failure stop still applies.

A failed check may only be excluded from the gate with evidence — a log showing it's unrelated infra flake, or a re-run that passes. "Probably a flake" on an empty log is not evidence.

## Step 8: Consolidate review feedback

Inspect the repository's configured review automation. Where present, the `AI code review` workflow and Cursor Bugbot post findings; wait for those configured checks and consolidate their output rather than duplicating the review locally. If neither is configured, report that and retain the reviews already required by the parent workflow; do not invent a bot gate.

1. Check whether this PR is an intermediate slice of an unmerged stack (its target base is another active feature branch, or successors are pending):
   - **Intermediate Stack PR**: Skip the 3-minute review-bot polling pause. Proceed directly; review-bot feedback is consolidated on the top-of-stack PR.
   - **Standalone or Top-of-Stack PR**: Wait for configured review bots to post — they often start only after CI is green. Poll, bounded to ~3 minutes:
   ```bash
   for i in $(seq 1 9); do
     gh pr checks <PR_NUMBER> --json name,state \
       --jq '.[]|select(.name|test("AI code review|bugbot|cursor";"i"))|"\(.name): \(.state)"'
     sleep 20
   done
   ```
   - `AI code review` check absent (author not on the allowlist) → just use Bugbot.
   - **If a review still hasn't posted after ~3 minutes → note it and proceed; don't block shipping on a review bot.**

2. Collect ALL findings from both — inline review comments and the sticky summary:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<PR_NUMBER>/comments --paginate \
     --jq '.[] | select(.user.login | test("cursor|bugbot|github-actions"; "i")) | {who: .user.login, path: .path, line: .line, body: .body}'
   gh api repos/{owner}/{repo}/issues/<PR_NUMBER>/comments --paginate \
     --jq '.[] | select(.user.login | test("cursor|bugbot|github-actions"; "i")) | {who: .user.login, body: .body}'
   ```
   (The AI review posts one sticky issue-comment marked `<!-- ai-code-review -->`; Bugbot posts inline review comments.)

3. Triage every finding from both sources together:
   - Valid + worth fixing → fix locally, run affected tests, commit (new commit), repeat Step 4 verification and Step 6's fingerprint/size gates, then push.
   - False positive / too noisy → skip.

4. After fixing, re-watch CI (Step 7). The CI review re-runs on the new push and refreshes its sticky comment; re-collect once more if you pushed fixes. **Cap at 2 review rounds** — don't chase every bot re-scan (diminishing returns).

## Red Flags — STOP

- About to push without a /verify verdict for this diff → back to Step 4; "tests pass" is not a verdict
- Fingerprint gate finds no record for the current tree, and Step 4 did not end in a declared 🔴 not-verifiable → the code changed after verification (or was never verified); re-verify, do not push
- "The only change since verify was a formatter / a comment" → re-verify anyway; the gate is content-based, not judgement-based
- Verification quietly skipped (missing tool, down server) → install the tool / start the server, or declare 🔴 loudly — silence is prohibited
- Size gate shows total > 500 (tests, docs and non-lockfile generated text included) → do not push or open the PR; restructure into coherent releasable increments
- Slice is under 500 lines but needs a later PR to work → do not ship it; revise the boundaries
- Compressing code or dropping tests to fit the cap → restore readability and coverage, then revise the boundaries
- "It's mostly tests" / "the app code is only 200 lines" → tests count; the reviewer reads the whole diff
- About to push to `main` directly → create a branch first
- About to force-push → ask user for confirmation
- No changes detected → do not create empty commits
- PR already exists → push to existing PR, don't create a new one
- 3+ CI fix iterations with no progress → stop and report

## Arguments

$ARGUMENTS — Optional: commit message, ticket ID, or notes.

### Parsing rules
- Matches a conventional commit prefix (`feat:`, `fix:`, etc.) → use as exact commit message
- Matches a ticket pattern (e.g., `INT-107`, `COR-456`) → include as ticket reference
- Empty → auto-detect commit type from the diff
- Anything else → treat as context for generating the commit message

Examples:
- `/ship` — auto-detect everything
- `/ship INT-107` — include ticket reference
- `/ship feat: Add concurrency tracking` — use this exact commit message
