# Review PR

Four-agent PR review: security, Rails patterns, code quality, and product domain.
Posts to GitHub when you're the author; shows inline when you're the reviewer.

> **Requires:** Run from inside the target repo's working tree. Context files (`docs/vision-and-ethos.md`, `CLAUDE.md`) are read from the current directory.

## Arguments

`$ARGUMENTS` — optional PR number, or `--fast` to skip.

### Parsing rules
- `--fast` → print "Review skipped (--fast)" and stop immediately
- A PR reference — `142`, `#142`, or a URL ending `/pull/<n>` → review that PR. Arbitrary text (e.g. a ticket like `COR-456`) does NOT match and falls through to branch detection.
- Empty → detect PR from current branch

## Step 0: Parse arguments

If `$ARGUMENTS` is `--fast`:
```
Review skipped (--fast)
```
Stop here.

If `$ARGUMENTS` is a PR reference — a bare number (`142`), `#142`, or a URL ending `/pull/<n>` — use that as the PR number. Do not extract a number from arbitrary text: a ticket like `COR-456` is not a PR number, so it falls through.
Otherwise detect from current branch:
```bash
gh pr view --json number -q '.number' 2>/dev/null
```
If that returns empty, tell the user no PR was found and stop.

## Step 1: Preflight checks

Run these in parallel:

```bash
# Verify gh is authenticated
gh auth status 2>&1

# Detect PR author
gh pr view <PR_NUMBER> --json author -q '.author.login' 2>/dev/null

# Detect current user
gh api user -q '.login' 2>/dev/null
```

**Failure modes — stop with a clear message if:**
- `gh auth status` fails → "Run `gh auth login` first"
- PR author fetch fails → "Could not find PR <number>"

Compare author to current user:
- Match → **author mode**: post to GitHub + show inline
- No match → **reviewer mode**: show inline only
- Current user can't be determined (`gh api user` empty/failed) → **reviewer mode** (inline only); note "couldn't confirm current user — not posting." Never post to a PR whose ownership can't be confirmed.

## Step 2: Fetch diff and context

Run in parallel:

```bash
# Fetch the diff (once — reuse for all agents)
gh pr diff <PR_NUMBER>

# List changed files (so agents can read them in full — see Step 3)
gh pr diff <PR_NUMBER> --name-only
```

```bash
# Check which context files exist
ls docs/vision-and-ethos.md 2>/dev/null && echo "vision: found" || echo "vision: missing"
ls docs/product-knowledge.md 2>/dev/null && echo "knowledge: found" || echo "knowledge: missing"
```

If `docs/vision-and-ethos.md` is missing → skip Agent 4 (product domain) and note in the review footer:
`⚠️ product-domain skipped — docs/vision-and-ethos.md not found`

If diff is empty → stop with:
"No diff found — nothing to review."

Read the following files:
- `docs/vision-and-ethos.md` (only if present — gates Agent 4; skip silently when absent)
- `docs/product-knowledge.md` (if it exists — skip silently if not)
- Extract the project's convention sections from `CLAUDE.md` — typically `## Architecture` and `## Conventions` (or equivalents such as `## Naming`) — by finding those level-2 headings (lines starting with exactly `## `) and reading until the next level-2 heading (not `###` subheadings). If `CLAUDE.md` only imports another file (e.g. a line like `@AGENTS.md`), resolve that import and extract the same sections from the imported file.

## Step 3: Run agents in parallel

Launch Agents 1–3 using the Agent tool simultaneously. Launch Agent 4 (product domain)
only if `docs/vision-and-ethos.md` was found in Step 2 — otherwise skip it. Pass the full
diff text in each prompt. Individual agent failures are non-fatal — proceed with whatever
returns.

**Read beyond the diff.** The diff shows only changed lines, so *omission* bugs — a
capability added to one code path but not its siblings — never appear in it. Each agent
should `Read` the changed files (listed in Step 2) in full from the working tree to inspect
unchanged code: sibling handlers, callers, the other half of a read/write pair. This is
reliable in author mode (working tree = PR branch); in reviewer mode the local tree may not
match the PR, so treat file reads as best-effort and fall back to diff-only reasoning when
they diverge.

### Agent 1: Security & Data Safety

Prompt:
```
You are a security-focused code reviewer for a Ruby on Rails application.

Review the following git diff for security issues. Focus only on security and data safety.

Look for:
- Mass assignment — params not filtered through `permit`
- Encrypted attribute mishandling — tokens, keys, PII stored or logged in plaintext
- Auth gaps — actions missing `require_login`, `User.find(params[:id])` instead of
  scoping to `current_user`
- Credential exposure — API keys or secrets in code or logs
- SQL injection via raw string interpolation
- Unsafe or open redirects
- Brakeman-class issues

Before flagging, sanity-check:
- "Credentials shipped to browser" — many SDK keys (analytics, embedded clients) are public/client-distributable by vendor design. Don't flag unless there's clear evidence the key is server-only (then IMPORTANT).
- "By-design" behaviour — if the cited code has a comment, spec reference, or obvious intent (anti-flicker, state-machine terminal, etc.), raise as a question, not a bug.

Severity calibration:
- CRITICAL — observable security hole an attacker can exercise on a realistic path.
- IMPORTANT — real risk that manifests under realistic conditions, not "if X and Y and Z all coincide."
- Below Important (hardening, low-probability edge cases, vendor confirmation, defence-in-depth, stylistic nits) — OUT OF SCOPE: drop it; do NOT relabel it as Important just to surface it.

Skip findings where the failure mode requires the system to already be broken at a deeper level (e.g. "could exfiltrate if the sandboxed worker is itself compromised" — the worker is the layer we trust).

Output format — one line per finding, pipe-delimited:
CRITICAL | <finding> | <impact> | <file:line>
IMPORTANT | <finding> | <impact> | <file:line>

Where:
- <finding> — what is wrong, ≤15 words. Lead with the symbol (method, class, attribute, file) in backticks when identifiable.
- <impact> — why it matters / what breaks, one sentence.
- <file:line> — location, e.g. `path/to/file.rb:42`. Use `model name` or `test suite` if no file applies. Multiple refs joined with ` · `.

If no findings: output `NONE` on its own line.

Be concise. Maximum 10 findings total. Prioritise the most significant.

<diff>
[INSERT FULL DIFF HERE]
</diff>
```

### Agent 2: Rails Domain Patterns

Prompt:
```
You are a Rails-specialist code reviewer. Review the following git diff for
Rails-specific antipatterns and convention violations.

Project conventions for context:
[INSERT THE CONVENTION SECTIONS EXTRACTED IN STEP 2 — e.g. Architecture, Conventions, Naming — verbatim]

Look for:
- N+1 queries — associations loaded in loops without includes/preload
- Synchronous work in controllers that belongs in a background job
- Job safety — not idempotent, not retry-safe, incorrect use of perform_later
- Service object shape violations (see conventions above)
- ActiveRecord misuse — update_attribute bypassing validations, save! swallowed in
  rescue, callbacks doing too much
- Missing database indexes on new foreign keys or frequently-queried columns
- find_or_create_by vs create! race condition risks

Before flagging, sanity-check:
- "Convention violation" claims — confirm the convention exists elsewhere in the same controller/file before calling something a violation. A divergent endpoint isn't a violation if no other endpoint in this file follows the supposed pattern.
- "Should be extracted to a service" claims — only flag if the action does meaningful work beyond a single update. A 3-line `update!` controller action does not need a `Dry::Monads` service.
- "Should rescue" claims — only flag if the unrescued exception will surface as a 500 to a real user request. If the input is typed and validated upstream (e.g. typed boolean from a TypeScript client), an unhandled `NotNullViolation` is acceptable telemetry.

Severity calibration:
- CRITICAL — production-affecting bug (data corruption, lost work, performance cliff under realistic load).
- IMPORTANT — real risk that will manifest under realistic conditions, not just "could theoretically happen."
- Below Important (stylistic, missing memoisation, deferred refactors, taste nits) — OUT OF SCOPE: drop it; do NOT relabel it as Important just to surface it.

Skip findings where the cited issue is an existing pattern in the controller/file that isn't being newly introduced by this PR — note as "out of scope" rather than flagging the PR for it.

Output format — one line per finding, pipe-delimited:
CRITICAL | <finding> | <impact> | <file:line>
IMPORTANT | <finding> | <impact> | <file:line>

Where:
- <finding> — what is wrong, ≤15 words. Lead with the symbol (method, class, attribute, file) in backticks when identifiable.
- <impact> — why it matters / what breaks, one sentence.
- <file:line> — location, e.g. `path/to/file.rb:42`. Use `model name` or `test suite` if no file applies. Multiple refs joined with ` · `.

If no findings: output `NONE` on its own line.

Be concise. Maximum 10 findings total. Prioritise the most significant.

<diff>
[INSERT FULL DIFF HERE]
</diff>
```

### Agent 3: Code Quality

Prompt:
```
You are a code quality reviewer. Review the following git diff for correctness,
edge cases, and test coverage. No domain knowledge assumed.

Look for:
- Logic errors — off-by-one, wrong boolean, inverted condition
- Unhandled edge cases — nil inputs, empty arrays, concurrent writes
- Cross-path consistency — a capability, field, or output added to one path but not its siblings (display vs copy/export/print/share, serialize vs deserialize, create vs update, read vs write, API vs UI). The omission lives in *unchanged* code, so read the full changed files, not just the diff. E.g. a transcript made visible on screen but still excluded from the copy/export handler and its enabling gate — shown and copied content silently diverge. Surface as IMPORTANT when users perceive the two paths as one.
- New code paths without corresponding tests
- Sibling-action test parity — when a feature adds new output/rendering, a test should exercise its sibling action (copy, export, submit) with the new data present, not just assert the render; a render-only test that skips the copy/export path is a real gap
- Tests that pass vacuously — not verifying real behaviour
- Dead code — unreachable branches, unused variables
- Methods doing too many things
- Naming that obscures intent

Before flagging, sanity-check:
- Race / ordering claims — read the actual statement order at the cited lines. `setRefA(...); setStateB(...);` in the same effect is sequential, not racing. Only flag a race if the two operations are in *different* effects, callbacks, or async boundaries with no enforced ordering.
- Stale-prop / stale-ref claims — check call frequency. A function called once at session start has no stale-prop problem. Only flag if the function is called repeatedly across renders and the captured value matters at each call.
- "Unbounded queue / unbounded growth" claims — only flag if there's a realistic path to sustained imbalance between producer and consumer. If unbounded growth requires the underlying system to already be broken (e.g. `process()` not running), the queue cap isn't the right fix.
- "Dead branch / unreachable fallback" — confirm the branch is genuinely unreachable, not just rarely hit. A defensive `?? performance.now()` may exist for type-narrowing reasons even if the runtime path is unreachable.

Severity calibration:
- CRITICAL — observable bug that breaks the feature for real users on a realistic path.
- IMPORTANT — real bug or risk that will manifest under realistic conditions, not "could happen if X and Y and Z all coincide."
- Below Important (stylistic, dead code, low-probability edge cases, hardening, taste nits) — OUT OF SCOPE: drop it; do NOT relabel it as Important just to surface it.

Skip findings where the failure mode requires the system to already be broken at a deeper level. "Defensive" findings (could fail if an upstream invariant is violated) are out of scope — skip them.

Output format — one line per finding, pipe-delimited:
CRITICAL | <finding> | <impact> | <file:line>
IMPORTANT | <finding> | <impact> | <file:line>

Where:
- <finding> — what is wrong, ≤15 words. Lead with the symbol (method, class, attribute, file) in backticks when identifiable.
- <impact> — why it matters / what breaks, one sentence.
- <file:line> — location, e.g. `path/to/file.rb:42`. Use `model name` or `test suite` if no file applies. Multiple refs joined with ` · `.

If no findings: output `NONE` on its own line.

Be concise. Maximum 10 findings total. Prioritise the most significant.

<diff>
[INSERT FULL DIFF HERE]
</diff>
```

### Agent 4: Product Domain

Prompt:
```
You are a product domain reviewer. Review the following git diff through a product
and user lens. Even backend-only changes can have user-visible consequences.

Product context:
[INSERT FULL CONTENT OF docs/vision-and-ethos.md]

[IF docs/product-knowledge.md EXISTS, INSERT:]
Domain knowledge:
[INSERT FULL CONTENT OF docs/product-knowledge.md]

Look for:
- Changes that affect what users see or experience, even indirectly
  (e.g. sync frequency → data freshness → user confidence in recommendations)
- Behaviour that contradicts the vision doc — noise over signal, late alerts,
  reduced trust, commercialisation over curation
- Anything in the domain knowledge this change touches or potentially invalidates
- Scope creep — the change does more than the PR description says
- User-facing consequences not mentioned in the PR description

Before flagging, sanity-check:
- "Behaviour contradicts the vision" claims — quote or paraphrase the specific vision statement being violated. Vague "this might erode trust" without a concrete vision-doc anchor is noise.
- "Scope creep" claims — only flag if a code change in the diff genuinely expands the PR's stated intent. Refactors and tightening incidental to the headline feature are not scope creep.

Severity calibration:
- CRITICAL — change that visibly degrades the user experience on a realistic path (e.g. silent data loss, broken core flow).
- IMPORTANT — real product risk that will affect users in normal use, with a concrete vision-doc or product-knowledge anchor.
- Below Important (copy / UX / scope nits, non-blocking product questions) — OUT OF SCOPE: drop it; do NOT relabel it as Important just to surface it.

Output format — one line per finding, pipe-delimited:
CRITICAL | <finding> | <impact> | <file:line>
IMPORTANT | <finding> | <impact> | <file:line>

Where:
- <finding> — what is wrong, ≤15 words. Lead with the symbol (method, class, attribute, file) in backticks when identifiable.
- <impact> — why it matters / what breaks, one sentence.
- <file:line> — location, or `n/a` for product-domain findings that don't tie to a single file.

If no findings: output `NONE` on its own line.

Be concise. Maximum 10 findings total. Prioritise the most significant.

<diff>
[INSERT FULL DIFF HERE]
</diff>
```

## Step 4: Synthesise findings

After all launched agents return, combine their outputs:

1. Collect all `CRITICAL | … | … | …` and `IMPORTANT | … | … | …` lines from each agent.
2. Deduplicate by topic — if two agents flag the same issue in different words, keep the most descriptive wording but the **highest** severity any agent assigned that topic (e.g. a CRITICAL + IMPORTANT pair on the same issue stays CRITICAL). Prefer false-positive duplicates over missed real findings.
3. Group by severity (Critical → Important). Number findings globally starting at 1 (Critical takes 1..N, Important continues from there).
4. Format the final comment using the layout below. Omit any severity section that has 0 findings — but always include the headline counts.

Layout:

```markdown
## AI Code Review &nbsp;·&nbsp; 🔴 N critical &nbsp;·&nbsp; 🟡 N important

<details>
<summary><b>🔴 Critical (N)</b></summary>

| # | Finding | Impact |
|---|---|---|
| 1 | <finding text><br><sub><file:line></sub> | <impact text> |
| 2 | … | … |

</details>

<details>
<summary><b>🟡 Important (N)</b></summary>

| # | Finding | Impact |
|---|---|---|
| 3 | … | … |

</details>

<sub>security · rails-patterns · code-quality · product-domain</sub>
```

Cell rules (keep tables inside the comment width — long unbreakable code spans force horizontal scroll):
- Finding cell: finding text on line 1, then `<br><sub>` wrapping the file ref on line 2, closed with `</sub>`.
- Wrap symbols (method, class, attribute) in backticks but keep them short.
- Multi-file refs: join with ` · `. For multiple lines in the same file, use `:42 · :108` shorthand.
- Aim for finding ≤ 18 words and impact ≤ 25 words. Tighten prose if cells overflow.

If every launched agent ran successfully and returned NONE → output (if a lens failed or timed out instead, keep the normal layout and mark that lens skipped in the footer per the rule below — do not claim "No findings"):

```markdown
## AI Code Review &nbsp;·&nbsp; ✅ No findings

<sub>security · rails-patterns · code-quality · product-domain</sub>
```

If any agent failed, timed out, or was skipped (e.g. `docs/vision-and-ethos.md` not present), replace its tag in the footer with `⚠️ <tag> skipped — <reason>`. Example:

`<sub>security · rails-patterns · code-quality · ⚠️ product-domain skipped — docs/vision-and-ethos.md not found</sub>`

## Step 5: Route output

**Always:** Display the formatted comment inline in the session.

**If author mode:** Post to GitHub:
```bash
gh pr comment <PR_NUMBER> --body "$(cat <<'REVIEW'
[INSERT FORMATTED COMMENT]
REVIEW
)"
```

## Step 6: Signal status for /ship integration

After displaying output, print one of these lines as the final line of output so that
`/ship` can parse the result when it invokes this command:

```
REVIEW_STATUS: CRITICAL
REVIEW_STATUS: INCOMPLETE
REVIEW_STATUS: OK
REVIEW_STATUS: CLEAN
```

- `CRITICAL` — one or more Critical findings exist
- `INCOMPLETE` — a review lens failed or timed out, so it did not run and coverage is partial (the intentional product-domain skip for a missing `docs/vision-and-ethos.md` does NOT count as incomplete)
- `OK` — Important findings only, and every launched lens ran
- `CLEAN` — no findings at all, and every launched lens ran

Precedence: any Critical finding → CRITICAL; else any lens that failed or timed out → INCOMPLETE (a failed or timed-out lens must never be reported as CLEAN; the intentional product-domain skip for a missing `docs/vision-and-ethos.md` does NOT trigger INCOMPLETE — those reviews can still be OK/CLEAN); else any Important → OK; else CLEAN.

`/ship` reads this line to decide whether to prompt the user (see ship.md Step 8).
