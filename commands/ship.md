# Ship

End-to-end workflow: format, branch, commit, verify UI locally, push, PR, fail-fast CI watch, consolidate review feedback.

## Workflow

```
Preflight → Format → Stage → Branch (if on main) → Commit → Verify UI (local, if UI changed)
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

Before anything, verify prerequisites:

```bash
git rev-parse --git-dir        # We're in a git repo
git status --porcelain         # There are changes to commit
gh auth status                 # GitHub CLI is authenticated
```

If there are no changes to commit, stop and tell the user.

Check for an existing PR on the current branch and capture its number for later steps:
```bash
PR_NUMBER=$(gh pr view --json number -q .number 2>/dev/null)
```
If `$PR_NUMBER` is set, a PR already exists — skip PR creation in Step 6 (just push) and reuse `$PR_NUMBER` in Steps 7–8. Otherwise Step 6 creates the PR; use that number from then on.

## Step 1: Format

Detect changed file types and run appropriate formatters:

```bash
# Tracked changes + untracked files
git diff --name-only HEAD
git ls-files --others --exclude-standard
```

Only run formatters for file types that actually changed:
- Ruby files (`.rb`) → `diffocop -A` (if available, else `bundle exec rubocop -A`)
- JS/TS/CSS files → `pnpm run format:fix && pnpm run lint:fix`

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

## Step 4: Verify UI locally (if applicable)

Before simplifying, determine whether the change touches UI (fetch first so `origin/main` is present):

```bash
git fetch origin main -q 2>/dev/null
git diff origin/main...HEAD --name-only | grep -E '\.(tsx?|jsx?|css|scss)$|^app/javascript/|^app/views/|^app/components/'
```

**If UI files changed**, verify against THIS clone's local dev server (parallel-dev setup), not staging:

1. Resolve this clone's dev-server port (each parallel-dev clone sets its own in `.env.local`):
   ```bash
   PORT=$(grep -E '^PORT=' .env.local | cut -d= -f2); PORT=${PORT:-3000}
   ```
2. Health-check that the server is actually up for THIS clone:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}"
   ```
   - `200`/`302` → up, continue.
   - Not up → start it in the **background** (never run `bin/dev` in the foreground — it blocks) and poll until ready:
     ```bash
     bin/dev >/tmp/dev-${PORT}.log 2>&1 &
     for i in $(seq 1 30); do curl -sf -o /dev/null "http://localhost:${PORT}" && break; sleep 2; done
     ```
     If it still isn't up after the wait, **skip local verify and note it** — don't block shipping.
3. Invoke verify-ui against the confirmed URL (`http://localhost:${PORT}`). It drives the local app with `agent-browser` — no staging deploy needed, so this runs before push. Determine the verification plan from the diff and the change's intent (your task / commit message) — exercise only the UI paths that changed, not the whole app.
4. If verify-ui surfaces a real breakage, fix it, re-stage, and commit before continuing. Verification is gating here (pre-push) — but only after the health-check confirms a real server; a down server is "skipped", not a breakage to chase.

**If no UI files changed:** skip this step.

## Step 5: Simplify

Before pushing, run `/simplify` to review changed code for reuse opportunities, quality issues, and efficiency improvements. This uses three parallel review agents (code reuse, code quality, efficiency) to catch issues locally before they go remote.

Invoke the `simplify` skill, which will:
1. Identify all changes via `git diff`
2. Launch three parallel review agents
3. Fix any issues found

If simplify made changes, stage and create a new commit before proceeding:
```bash
git add <changed files>
git commit  # New commit with fixes from simplify
```

If no issues were found, proceed directly to push.

If `/simplify` changed any UI files (same globs as Step 4), re-run Step 4's local verification before pushing — those edits weren't covered by the earlier pass.

## Step 6: Push + Create PR

```bash
git push -u origin <branch-name>
```

If no PR exists yet, create one with `gh pr create`.

### Writing the body

Invoke the **`writing-pr-descriptions`** skill and follow it exactly — it owns the format (What / Why / Worth-noting), the 3-bullet / 2–3-sentence section caps, and the hard rules (one idea per sentence, outcome not inventory, stack etiquette, no Fixes footer, no attribution).

### Creating the PR

Write the body to a temp file (Write tool or an editor) and pass it with `--body-file` — never inline the body in `--body "..."` or a heredoc, because backticks in the body get shell-evaluated and mangle it. Capture the new PR's number so Steps 7–8 can use it:

```bash
gh pr create --title "feat: Title here [TICKET-ID]" --body-file /tmp/pr-body.md
PR_NUMBER=$(gh pr view --json number -q .number)
```

## Step 7: Watch CI (fail fast)

Watch only the **required** checks and bail the instant one fails — don't block on slow non-required checks (branch deploy, Chromatic, the review bots). Wait for checks to register first, or `--watch` hits a "no checks yet" race right after PR creation, returns non-zero, and falsely trips the fix loop:

```bash
for i in $(seq 1 12); do
  n=$(gh pr checks <PR_NUMBER> --json name --jq 'length' 2>/dev/null || echo 0)
  [ "${n:-0}" -gt 0 ] && break
  sleep 5
done
gh pr checks <PR_NUMBER> --watch --fail-fast --required --interval 20
```

- **Exit 0** → all required checks passed → go to Step 8.
- **Non-zero** → a required check failed and `--fail-fast` bailed immediately. Fix it now:
  1. Identify the failed check(s): `gh pr checks <PR_NUMBER> --required` (look for `fail`/`X`).
  2. Fetch the errors:
     - RSpec → use `.claude/skills/fetching-ci-errors/fetch_ci_errors` if present.
     - ESLint / TypeScript / Prettier / other → find the failed run, then view its log: `gh pr checks <PR_NUMBER> --json name,bucket,link --jq '.[]|select(.bucket=="fail").link'`, then `gh run view <run-id> --log-failed` (run-id from that link).
  3. Fix locally, run to verify, commit (new commit, NOT amend), push.
  4. Re-run the watch. **Max 3 fix rounds**, then stop and report.

Why these flags:
- `--fail-fast` returns on the first failure, so you fix immediately instead of waiting for the whole suite.
- `--required` ignores noisy non-required checks (Chromatic, Bugbot, the AI review) so the watch can't hang on slow/irrelevant ones — those are handled in Step 8.

## Step 8: Consolidate review feedback

Code review now runs automatically in CI: the `AI code review` workflow posts a four-agent + correctness comment, and Cursor Bugbot posts its own. **Don't run `/review-pr` locally** — wait for both and act on their combined output.

1. Wait for both review bots to post — they're non-required (Step 7's `--required` watch didn't wait for them) and often start only after CI is green. Poll, bounded to ~3 minutes:
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
   - Valid + worth fixing → fix locally, commit (new commit), push.
   - False positive / too noisy → skip.

4. After fixing, re-watch CI (Step 7). The CI review re-runs on the new push and refreshes its sticky comment; re-collect once more if you pushed fixes. **Cap at 2 review rounds** — don't chase every bot re-scan (diminishing returns).

## Red Flags — STOP

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
