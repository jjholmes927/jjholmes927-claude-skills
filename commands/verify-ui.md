# Verify UI

Verify UI changes in a real browser using `agent-browser` after completing implementation work.

**Claims about UI correctness without browser evidence are assumptions, not facts.**

<EXTREMELY-IMPORTANT>
NO "IT LOOKS GOOD" WITHOUT A SCREENSHOT OR SNAPSHOT CONFIRMING IT.

Invoke this command when:
1. A UI feature, component, or page has just been implemented or modified
2. A bugfix that affects visible UI or user workflow has been completed
3. The user asks to "verify", "check", or "test" a UI change in the browser
</EXTREMELY-IMPORTANT>

## When to Use

- After implementing or modifying a UI component, page, or visual element
- After fixing a bug that affects visible UI behavior
- When the user explicitly asks to verify, check, or test a UI change in a real browser
- After touching CSS, templates, view files, or frontend JavaScript that changes rendered output

## When NOT to Use

- After backend-only changes (API logic, database migrations, background jobs)
- For automated test suites — use the project's test runner instead
- For verifying non-visual behavior (API responses, data processing)
- When there is no running target (no localhost, no PR with staging deployment, and no URL provided)
- For TypeScript type refactors, build config changes, or utility function changes with no visual impact

## Arguments

$ARGUMENTS — Optional: target URL, PR reference, or empty for auto-detect.

### Parsing rules
- Full URL (`https://...`) → use as target directly
- PR reference (`#6715`, `6715`, `https://github.com/.../pull/6715`) → resolve staging URL from PR deployment
- Empty → auto-detect (see Target Resolution)

## Target Resolution

Before running any verification, resolve the target URL:

### Step 0a: Check agent-browser is available

```bash
which agent-browser
# If not found: npm i -g agent-browser && agent-browser install
```

If not found, report the issue and stop.

### Step 0b: Resolve target URL

Derive the repo and staging session name once:
```bash
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
SESSION_NAME="$(basename "$REPO")-staging"
```

**If arguments contain a full URL** → use it directly.

**If arguments contain a PR reference** (e.g., `#6715`, `6715`, GitHub PR URL):
1. Extract PR number (regex: `(\d+)` from the input)
2. Get the latest deployment URL (note: use double quotes for shell variable expansion in the jq filter):
   ```bash
   PR_NUMBER=6715  # extracted from input
   DEPLOYMENT_JSON=$(gh api "repos/${REPO}/deployments?per_page=100" \
     --jq "[.[] | select(.payload | fromjson? | .pr_number == ${PR_NUMBER})] | sort_by(.created_at) | last")
   ```
   If `$DEPLOYMENT_JSON` is empty or `null`, report: "No deployment found for PR #N. The branch may not have been deployed yet." and stop.
3. Extract `web_url` from the deployment payload (the `.payload` field is a JSON string — parse it to get `.web_url`)
4. Extract the deployment ID from `$DEPLOYMENT_JSON` and check deployment status:
   ```bash
   DEPLOYMENT_ID=$(echo "$DEPLOYMENT_JSON" | jq -r '.id')
   gh api "repos/${REPO}/deployments/${DEPLOYMENT_ID}/statuses" --jq '.[0].state'
   ```
   - `success` → proceed
   - `failure` → report "Deployment failed" and stop
   - `pending` / `in_progress` → wait 30s and retry (up to 5 minutes total)
5. Health check:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" --max-time 30 "<staging_url>"
   ```
   Accept 200 or 302 as healthy. Retry up to 3 times with 10s gap (cold start). If still unhealthy, report and stop.

**If no arguments provided:**
1. Resolve this clone's dev-server port from `.env.local` (each parallel-dev clone sets its own; defaults to `3000` if unset), then health-check it: `PORT=$(grep -E '^PORT=' .env.local | cut -d= -f2); PORT=${PORT:-3000}; curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}"`
   - If 200 → use `http://localhost:${PORT}` as target
2. If localhost not running, check for PR on current branch:
   ```bash
   gh pr view --json number --jq '.number' 2>/dev/null
   ```
   - If PR found → resolve staging URL using the PR flow above
   - If no PR → report "No target found. Provide a URL, PR number, or start the dev server." and stop.

**When called from ship**, ship passes the local dev server URL for the current clone (parallel-dev setup) — use it directly. PR/staging resolution applies only when given an explicit PR reference.

Set `$TARGET_URL` to the resolved URL for all subsequent steps. Set `$IS_STAGING` to true if the target is not localhost.

## Five-Step Pattern: Open, Locate, Act, Verify, Cleanup

**Staging timeout:** When verifying against staging, the entire verification flow has a 7-minute maximum. If exceeded, report what was completed so far and proceed to cleanup.

### Step 1: Open

Navigate to the page where changes were made.

**Localhost:**
```bash
agent-browser open $TARGET_URL/path/to/page
agent-browser wait --load networkidle
```

**Staging** (when `$IS_STAGING` is true):
```bash
agent-browser --session-name $SESSION_NAME open $TARGET_URL/path/to/page
agent-browser wait --load domcontentloaded
```

Use `domcontentloaded` instead of `networkidle` for staging — remote environments are slower and `networkidle` tends to timeout.

If the page redirects to a login URL (Kinde, Google, Okta), follow the Authentication section to re-establish the session.

### Step 2: Locate

> **Staging note:** When `$IS_STAGING` is true, prefix all `agent-browser` commands with `--session-name $SESSION_NAME`.

Take a snapshot to discover interactive elements and understand the page state.

```bash
agent-browser snapshot -i
# Output: @e1 [input type="email"], @e2 [button] "Save", @e3 [link] "Back"
```

For visual verification, use annotated screenshots:
```bash
agent-browser screenshot --annotate
```

For full-page captures on long pages:
```bash
agent-browser screenshot --full --annotate
```

**Alternative: semantic locators** when you know the expected element:
```bash
agent-browser find role button --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "test@test.com"
```

### Step 3: Act

> **Staging note:** When `$IS_STAGING` is true, prefix all `agent-browser` commands with `--session-name $SESSION_NAME`.

Interact with the page to exercise the workflow that was changed.

```bash
agent-browser fill @e1 "test@example.com"
agent-browser click @e2
agent-browser wait --load networkidle
```

<EXTREMELY-IMPORTANT>
**Refs expire after navigation or DOM changes.** After any click, form submission, or action that mutates the page, you MUST re-snapshot before using refs:

```bash
agent-browser snapshot -i  # Get fresh refs after DOM changes
```
</EXTREMELY-IMPORTANT>

### Step 4: Verify

> **Staging note:** When `$IS_STAGING` is true, prefix all `agent-browser` commands with `--session-name $SESSION_NAME`.

Confirm the UI state changed as expected.

```bash
# Re-snapshot for fresh refs
agent-browser snapshot -i

# Check text content
agent-browser get text @e5

# Take a screenshot for visual confirmation
agent-browser screenshot --annotate verification.png

# Check the current URL (e.g. after redirect)
agent-browser get url

# Check for JavaScript errors
agent-browser errors

# Additional get commands: get html, get value, get attr, get count, get styles
```

For responsive verification:
```bash
agent-browser set viewport 375 812   # iPhone-sized
agent-browser screenshot --full mobile.png
agent-browser set viewport 1280 720  # Desktop
agent-browser screenshot --full desktop.png
```

### Step 5: Cleanup (MANDATORY)

Close the browser session. Skipping this leaves zombie browser processes.
`agent-browser close` preserves session-name state — your staging auth will persist for next time.

```bash
agent-browser close
```

## Authentication

### Localhost
No auth required — the dev server runs unauthenticated locally.

### Staging (any non-localhost target)

All `agent-browser` commands MUST include `--session-name $SESSION_NAME` to persist auth cookies across runs.

After opening the page, detect auth state:

1. Take a snapshot: `agent-browser --session-name $SESSION_NAME snapshot -i`
2. Check for app elements (nav links like "Home", "Settings", "Sign out") → **authenticated**
3. Check for login elements (text "Email", "Sign in", "Kinde", "Google", "Okta") → **not authenticated**

If not authenticated:
1. Report to the user:
   ```
   Staging session expired or not set up. Please log in manually:
   ! AGENT_BROWSER_HEADED=true agent-browser --session-name $SESSION_NAME open "<TARGET_URL>"
   Log in through the SSO flow, then come back and confirm.
   ```
2. Stop and wait for user confirmation
3. After user confirms, close the headed browser and retry verification from the Open step

**Note:** `agent-browser close` preserves session-name state. Sessions survive close/reopen cycles. Session expiry timeline varies — if auth fails, the skill will prompt for re-login.

## Reporting Template

After verification, report using this structure:

````
## UI Verification: [local dev server / PR #N / URL]
**URL:** [target URL]
**Result:** PASS / FAIL

### What was verified
- [x] Description of check 1
- [x] Description of check 2
- [ ] Description of failed check (with details)

### Screenshots
- screenshot-1.png — description
- screenshot-2.png — description

### Console errors
None / list of errors

### Issues found
None / list of issues with severity
````

This summary lets the developer async-review what was validated without being blocked.

## Red Flags — STOP

If you catch yourself thinking:
- "The code change is obviously correct, no need to check"
- "I already verified mentally by reading the template"
- "Browser verification would take too long"
- "It's just a CSS change, it'll be fine"
- "The tests pass, so the UI must be correct"

**STOP. These are exactly the cases where browser verification catches real issues.**

## Common Scenarios

> **Wait strategy:** Use `networkidle` for localhost, `domcontentloaded` for staging. The examples below show `networkidle` — substitute `domcontentloaded` when targeting staging.

### Visual Check (no interaction needed)
```bash
agent-browser open $TARGET_URL/page && agent-browser wait --load networkidle
agent-browser screenshot --annotate
```

### Form Workflow
```bash
agent-browser open $TARGET_URL/form
agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser fill @e1 "Test Value"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # Re-snapshot after DOM change
agent-browser get text body
agent-browser screenshot after-submit.png
```

### Responsive Check
```bash
agent-browser open $TARGET_URL/page && agent-browser wait --load networkidle
agent-browser set viewport 375 812
agent-browser screenshot --full mobile.png
agent-browser set viewport 1280 720
agent-browser screenshot --full desktop.png
```

### Console Error Check
```bash
agent-browser open $TARGET_URL/page && agent-browser wait --load networkidle
agent-browser snapshot -i
agent-browser click @e1
agent-browser wait --load networkidle
agent-browser errors
agent-browser console
```
