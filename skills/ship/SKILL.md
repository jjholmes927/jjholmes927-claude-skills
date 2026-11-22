---
name: ship
description: End-to-end PR workflow — format, commit, verify behaviour with evidence (always, via /verify), push, open the PR, watch CI fail-fast, consolidate Bugbot and AI-review feedback, then land the PR and check production where the repository opts in. Use when work is ready to become a pull request, or the user asks to ship it.
---

# Ship

End-to-end workflow: format, branch, commit, verify with evidence, push, PR, fail-fast CI watch, consolidate review feedback, land on green and check production after the deploy where the repository opts in.

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
                    Land on green (opt-in repos only)
                                    │
                Check production after deploy (opt-in repos only)
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

When the caller supplies approved acceptance criteria (E2E passes them from `.e2e/handoff.md`), give them to /verify so its promises come from the approved plan, not only the diff. When the base branch's guide (`origin/$PR_BASE_BRANCH`, never this checkout; Step 9 condition 1's read with Step 10's line) has the production-check line, tell /verify: it marks promises only production can show `checked after deploy`, and Step 10 must check each one.

Collect configured lint advisories with `python3 -B
${CLAUDE_PLUGIN_ROOT}/skills/e2e/scripts/advisory_review.py scan "$BASE"
--harness <actual-harness> --workflow ship` (one shell line). Reuse an E2E report
only when that entry point's `check` succeeds for the current tree. Read
`.e2e/lint-advisories.md` and record each affected finding using `decide <id>
<fixed|kept|dismissed> '<reason>'`. Fixed claims trigger a verification scan;
thresholds alone do not require extraction or a P2 finding. Resolve blocking
defects and incomplete tools, and require `check` before publication. After any
repair, rescan and renew affected decisions; the existing repair budgets apply.

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

Watch all checks and bail the instant one fails. Do NOT use `--required`: most of our repos configure no branch-protection required checks, so `--required` returns "no required checks reported" and the watch silently no-ops — this failed in every such repo it was tried in. Wait for checks to register first, or `--watch` hits a "no checks yet" race right after PR creation, returns non-zero, and falsely trips the fix loop:

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
  4. Re-run the watch. **Stop as soon as a round makes no progress** (the same check fails with the same error after your fix), and never run more than 3 fix rounds. The stop report lists each round in one line (what failed, what you changed) and ends with the one question the user must answer to unblock it.

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

## Step 9: Land on green (opt-in repositories only)

Merging deploys in many repositories, so landing is opt-in per repository. Leave the merge to the user unless **every** condition holds:

1. The repository guide **on the base branch** contains the line `**Merge policy: agents merge their own PRs once required checks pass.**` Never read it from this checkout: a PR that adds the line must not be able to merge itself.
   ```bash
   git fetch -q origin "$PR_BASE_BRANCH"
   for f in CLAUDE.md AGENTS.md; do git show "origin/$PR_BASE_BRANCH:$f" 2>/dev/null; done \
     | grep -qF '**Merge policy: agents merge their own PRs once required checks pass.**' && echo "opted in" || echo "NOT opted in"
   ```
2. The base branch requires status checks, through branch protection or a ruleset. Output that is not a number (an error body, a 404) counts as 0:
   ```bash
   classic=$(gh api "repos/{owner}/{repo}/branches/$PR_BASE_BRANCH/protection/required_status_checks" --jq '.checks | length' 2>/dev/null)
   rules=$(gh api "repos/{owner}/{repo}/rules/branches/$PR_BASE_BRANCH" --jq '[.[] | select(.type == "required_status_checks")] | length' 2>/dev/null)
   case "$classic" in ''|*[!0-9]*) classic=0;; esac
   case "$rules" in ''|*[!0-9]*) rules=0;; esac
   [ $((classic + rules)) -gt 0 ] && echo "required checks present" || echo "NO REQUIRED CHECKS"
   ```
3. The PR's base is the repository's default branch (stacked PRs: see below).
4. The /verify verdict for the pushed tree is ✅ for every promise, or `checked after deploy` where Step 4 found the production-check line.
5. Steps 7 and 8 ended green on this PR's head, every configured review bot has posted on this PR (an intermediate stack PR waits for them here, because Step 8 skipped that wait), no P1/P2 finding is unresolved, and the PR is not a draft.

When all hold, queue the merge pinned to the verified head. If the command fails (for example, the repository has auto-merge switched off), hand back; never retry with `--admin` or without `--auto`:

```bash
gh pr merge <PR_NUMBER> --auto --squash --match-head-commit "$(git rev-parse HEAD)" || echo "AUTO-MERGE NOT QUEUED"
```

Then poll until the PR merges, closes or fails a required check. One poll call stays under eight minutes; repeat it up to four times (about 30 minutes in all), or run it in the background where the harness supports that:

```bash
for i in $(seq 1 24); do
  state=$(gh pr view <PR_NUMBER> --json state --jq .state)
  failed=$(gh pr checks <PR_NUMBER> --required --json bucket --jq 'any(.[]; .bucket == "fail")' 2>/dev/null)
  { [ "$state" != "OPEN" ] || [ "$failed" = "true" ]; } && break
  sleep 20
done
gh pr view <PR_NUMBER> --json state,mergeCommit --jq '"\(.state) \(.mergeCommit.oid)"'
```

MERGED: record the merge commit SHA in the ship summary and the task handoff. Anything else after 30 minutes (still open, closed, or a failed required check): leave auto-merge queued, report the state and hand back. Where the guide opts into the production check, say that Step 10 will not run when the PR merges later.

**Stacks land bottom-up, in the same ship run.** Run this step for the bottom PR first. A child PR whose base is another feature branch fails condition 3 only for now: wait here for its parent's result rather than handing back. When the parent merges, GitHub retargets the child to the default branch only if the repository deletes head branches on merge (`gh api repos/{owner}/{repo} --jq .delete_branch_on_merge`). Once it is retargeted, rebase the child onto the default branch if GitHub reports it behind or conflicting, re-run Step 4 and the Step 6 gates for any change, push, re-watch CI, then run this step for it. Hand back if the parent hands back, or if the child is not retargeted within five minutes of the parent merging.

When any condition fails, name it in the ship summary. In Kandev, ask the user to merge through the question tool and include that reason.

## Step 10: Check production (opt-in repositories only)

/verify proved the branch; production runs what landed on main. Run this step only when Step 9 merged the PR in this run **and** main as it stood before this run's first merge contains the line `**Production check: agents verify production after their PRs deploy.**` in CLAUDE.md or AGENTS.md. That commit is `$BEFORE_SHA`: `$MERGE_SHA^` for a single PR (`$MERGE_SHA` is the merge commit Step 9 recorded), or the parent of the first slice's merge commit for a stack. Read the line and the recipe it links only from `$BEFORE_SHA`, never from this checkout or from main after a merge: no PR, and no slice of a stack, may opt itself in or write its own recipe. Give verify that recipe text. Each shell call is fresh, so re-derive a lost SHA (`gh pr view <PR_NUMBER> --json mergeCommit --jq .mergeCommit.oid`) rather than run with it unset:

```bash
git fetch -q origin "$PR_BASE_BRANCH"
: "${BEFORE_SHA:?set it from Step 9's merge commit}"
LINE=$(for f in CLAUDE.md AGENTS.md; do git show "$BEFORE_SHA:$f" 2>/dev/null; done \
  | grep -F '**Production check: agents verify production after their PRs deploy.**' | head -n 1)
RECIPE=$(printf '%s' "$LINE" | sed -n 's/.*](\([^)#]*\)[)#].*/\1/p')
if [ -z "$LINE" ]; then echo "NOT opted in"
elif [ "$(git cat-file -t "$BEFORE_SHA:$RECIPE" 2>/dev/null)" != blob ]; then echo "RECIPE UNREADABLE"
else git show "$BEFORE_SHA:$RECIPE"; fi
```

- **NOT opted in** → skip this step: ship is done. Say so in the ship summary; there is nothing to ask the user.
- **RECIPE UNREADABLE** → the line is there but its recipe is missing: no check. Report it and ask the user.

The recipe owns every repository fact: production URL, deploy signal, login and account rules, read-only data path, error and health checks, agent identity. Never fill a gap with a guess; a fact it does not state is a check you could not run (🟡). A stack checks once, after its last PR merges (`$MERGE_SHA` is that merge), with every landed slice's criteria.

**1. Wait for the deploy.** A newer push to main can cancel the CI run for `$MERGE_SHA`, so watch every main commit that contains it. The loop needs two recipe facts: the **Deploy signal**, a commit-status context (`$DEPLOY_CONTEXT`), and the **Deploy gating workflow** whose success triggers the deploy (`$GATING_WORKFLOW`). Other workflows never count. For another kind of signal, poll it with the same bounds and rules. One call stays under eight minutes; repeat it up to four times (about 30 minutes in all), or run it in the background where the harness supports that:

```bash
: "${MERGE_SHA:?}" "${PR_BASE_BRANCH:?}" "${DEPLOY_CONTEXT:?}" "${GATING_WORKFLOW:?}"
for i in $(seq 1 14); do
  git fetch -q origin "$PR_BASE_BRANCH"
  rows=$(for sha in $(git rev-list --ancestry-path "$MERGE_SHA..origin/$PR_BASE_BRANCH") "$MERGE_SHA"; do
    deploy=$(gh api "repos/{owner}/{repo}/commits/$sha/status" --jq "[.statuses[] | select(.context == \"$DEPLOY_CONTEXT\") | .state][0] // \"none\"")
    gate=-
    [ "$deploy" = none ] && gate=$(gh run list --commit "$sha" --workflow "$GATING_WORKFLOW" --json status,conclusion --jq '.[0] | if . == null then "none" elif .status != "completed" then .status else .conclusion end')
    echo "$sha deploy=$deploy gate=$gate"
  done)
  echo "$rows"
  echo "$rows" | grep -q 'deploy=success' && break
  echo "$rows" | grep -qE 'deploy=pending|deploy=none gate=success' || { echo "$rows" | head -n 1 | grep -qE 'deploy=(failure|error)|gate=[a-z_]*failure' && break; }
  sleep 30
done
```

Every row contains `$MERGE_SHA`; the first row is the newest. Read them in order:
- Any row `deploy=success` → record the newest such commit as `$DEPLOYED_SHA` and continue.
- Any row `deploy=pending`, or a passed gating workflow with no deploy status yet (the deploy job sets it only once it starts) → keep waiting.
- Otherwise the newest row decides: `deploy=failure` or `error` → **deploy failed**; its gating workflow **failed** → **main CI red, deploy skipped**. A failure on an older row, or in any other workflow, is not this.
- A **cancelled** run means a newer commit superseded it: keep waiting on the newer commit.
- Still waiting after 30 minutes → **deploy timed out**.

Deploy failed, skipped or timed out: stop and hand back. There is no production verdict to give and no revert PR to open; report the last state where step 4 would post a verdict.

**2. Check production.** Invoke /verify with a production target: the recipe, `$DEPLOYED_SHA` and the approved acceptance criteria. It keeps the promises observable in production, including every one marked `checked after deploy` before the merge, and adds the recipe's error and health checks.

**3. Verdict**, stamped `Production check @ $DEPLOYED_SHA`. First re-list main's deploys: another commit in the deployed range, or one deployed during the check, shares the window.
- ✅ every promise observable in production passed and no new error type appeared. A PR with nothing user-visible gets ✅ labelled "nothing user-visible; data checks and errors clean". verify's `Deferred:` list doesn't block ✅.
- 🟡 something could not be checked (say what), the health check reports degraded while liveness passes, or another PR shares the window and a new error cannot be pinned on this PR alone (name both SHAs). Shared attribution is never 🔴: two agents must not open competing reverts.
- 🔴 a promise of this PR fails in production, a new error type's route or stack touches this PR's files, or the liveness check fails.

**4. Post and act.** Write the verdict to a file whose first line is exactly `## Production check @ <DEPLOYED_SHA>` (an emoji may follow), so it can be found by search. Then give each promise with its evidence, every query with its result, the error comparison, the health responses, the `Deferred:` list and where the screenshots are. Post it where the recipe allows, never with `gh pr comment` as the user:
- **Agent identity** in the recipe (a command that stands in for `gh` and posts as the agent's own account) → `<agent identity> pr comment <PR_NUMBER> --body-file <file>`. When a Linear ticket exists, add a one-line ticket comment linking to the comment URL it prints.
- No agent identity → the verdict itself is the ticket comment.
- No ticket either → the handoff and your final message only.

Attach the screenshots to the ticket through the Linear connector (`prepare_attachment_upload`, a raw PUT of the file with the signed headers, then `create_attachment_from_upload`, one file at a time); without a ticket, keep their paths in the handoff. Never create a Linear issue. Copy the verdict into the ship summary and the task handoff.
- ✅ → done.
- 🟡 → report what was not checked and ask the user (in Kandev, through the question tool). No revert PR.
- 🔴 → don't ask yet: the comment above reports it, so add it to the handoff and any ticket comment and go straight on. Open a revert PR: a branch from the updated base named per Step 2 and ending `-revert-<PR_NUMBER>`, and `git revert --no-edit "$MERGE_SHA"`. If the revert conflicts, `git revert --abort` and hand back with the conflict; never resolve it. Run /verify on its one promise, "back to pre-merge behaviour", with the revert commit's diff inverting `$MERGE_SHA` as the evidence, then Step 6 to open the PR. Skip Step 5 and review fixes so it stays a clean revert. A stack gets one revert PR per landed slice, each reverting that slice's merge commit, newest first and each based on the one before. Then ask the user once with the evidence and the revert PR links (in Kandev, through the question tool) and hand back, without waiting on CI or bots. Never run Step 9 or this step on a revert PR and never merge it, whatever the merge policy says.

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
- A CI fix round leaves the same check failing with the same error → stop and report; don't spend the remaining rounds
- About to queue auto-merge when the base branch's guide has no merge-policy line (including a PR that adds the line), or the base has no required checks → don't; hand the merge to the user
- About to run Step 10 because the production-check line or recipe is in this checkout or in main after a merge → read both from `$BEFORE_SHA`; no PR or stack slice opts itself in
- About to merge a revert PR, or run Step 9 on one → don't; the user decides on every revert
- About to post a production verdict with `gh pr comment` as the user → post through the recipe's agent identity, or fall back to the ticket or handoff
- About to click a review-queue or admin action, or anything else the recipe's account rules forbid, as the production account → don't; that promise is 🟡 not checked
- About to read production through `rails runner`, a console or SSH → use the recipe's read-only path; application code can send email, call APIs or enqueue jobs
- A production ✅ for a UI promise without screenshots → it is not a ✅
- Treating a cancelled main CI run as a failure → a newer commit superseded it; wait on that commit's deploy

## Arguments

$ARGUMENTS — Optional: commit message, ticket ID, or notes.

### Parsing rules
- Matches a conventional commit prefix (`feat:`, `fix:`, etc.) → use as exact commit message
- Matches a ticket pattern (e.g., `INT-107`, `COR-456`) → include as ticket reference
- Empty → auto-detect commit type from the diff
- Approved acceptance criteria (passed by E2E) → give them to /verify in Steps 4 and 10; never use them as the commit message
- Anything else → treat as context for generating the commit message

Examples:
- `/ship` — auto-detect everything
- `/ship INT-107` — include ticket reference
- `/ship feat: Add concurrency tracking` — use this exact commit message
