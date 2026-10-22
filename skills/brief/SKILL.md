---
name: brief
description: "Generate the user's morning chief-of-staff brief — Must act / Waiting on you / Today / Commitments detected, ≤200 words with hard caps. Use when the user says 'brief', 'morning brief', or 'what needs me today'."
argument-hint: [optional focus, e.g. "people" or "delivery"]
---

# Morning Brief — /brief

Chief-of-staff v0: one shot, push-format. Born from the 2026-08 workflow analysis — machine-owned loops ran 9/9 while user-initiated loops ran ~0/9 — so this command owns the initiation and leaves the user only the judgment.

State lives in `~/.claude/cos/`: `sources.md` (rosters, timezone, scope — edit there, never here), `ledger.md` (open commitments), `briefs/` (the archive). If the directory is missing, create it and seed empty files rather than stopping.

## Collect — read-only, metadata before bodies

Read `~/.claude/cos/sources.md` and `ledger.md` first. Resolve the GitHub login via `gh api user --jq .login` (brag-doc convention); on auth failure report `gh auth login` as the fix — never render it as a quiet empty source. Load deferred MCP schemas in ONE call:

`ToolSearch("select:mcp__claude_ai_Google_Calendar__list_events,mcp__claude_ai_Gmail__search_threads,mcp__claude_ai_Slack__slack_search_public_and_private,mcp__linear-server__list_issues")`

Then run all collectors in parallel. Never fetch a body until the item survives its metadata filter.

| Source | Call (cheap form) | Keep only |
|---|---|---|
| Calendar | ONE `list_events` spanning today + tomorrow, `orderBy: startTime`, timezone from sources.md. Attendee response status and leave (`OUT_OF_OFFICE` events) come from this same response — never call `get_event` | double-bookings, meetings needing prep, unconfirmed attendees on meetings the user organises, meetings still accepted on leave days |
| Linear | `list_issues` assignee=me state=started; plus priority=1 with `team` from sources.md, `includeArchived: false`, `limit: 20`, `fields` without `description` | merge/park decisions, items stalled >7 days, due dates |
| GitHub | `gh search prs --review-requested=<login> --state=open --json number,title,repository,updatedAt,isDraft --limit 20`; second call with `--author=<login>` (GitHub ANDs qualifiers — the split is required) | review requests with age; own PRs quiet >48h |
| Gmail | ONE OR-grouped query: `in:inbox newer_than:1d {from:…}` built from sources.md senders, plus Drive access requests | deadlines, overdue chases, access requests blocking a person — the ledger owns anything older than a day |
| Slack | `to:me -from:me after:<last brief date>`, `sort: timestamp`, one page; judge "no reply yet" from each hit's included context, `slack_read_thread` only when context is truncated | human asks with no reply; drop bots and social chat |
| Ledger | `~/.claude/cos/ledger.md` | every open commitment carries forward until done or dismissed |

A failed collector never stops the run — a partial brief beats none (deliberate divergence from pick-up-linear-ticket's stop rule).

## Compose

≤200 words across the four section bodies (title and footer excluded — `wc -w` once, on the written file), exactly these sections:

- **Must act** — ≤3 items, each time-sensitive today with the deadline named. Within the cap, warnings outrank non-warnings and a blocked person outranks a blocked ticket. A dropped 4th item simply waits for tomorrow's run — collectors re-read live sources, so only commitments need persisting.
- **Waiting on you** — decisions only the user can make. An item's third consecutive appearance must propose escalation, reassignment, or an explicit kill — never a bare "still waiting".
- **Today** — one line of schedule, conflicts flagged ⚠️, rota state noted.
- **Commitments detected** — ≤3, explicit and source-linked only, never inferred from vague discussion. The user's own promises rank first.

Footer — one line of per-source freshness in verify's taxonomy: `✓` swept clean · `🟡 partial: <what's missing>` (e.g. pagination stopped early, window truncated) · `🔴 FAILED: <fix>`. A silently absent source is a defect of this command. An empty section prints "— none".

## Deliver and record

1. Write the brief to `~/.claude/cos/briefs/brief-YYYY-MM-DD.md`, then print the same text in chat — no read-back.
2. Update `ledger.md`: append new commitments as `date · source · promise · delete when`; remove entries the user marked done or dismissed this run.
3. No send, post, label, or ticket-write calls — ever. A requested reply is drafted through /newspaper for the user to paste; never fabricate a source's content.

## Arguments

$ARGUMENTS — optional focus (e.g. "people", "delivery"): restrict the Collect table to matching sources. Empty → all six.
