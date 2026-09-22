---
name: investigate
description: "Use when the user says /investigate, 'root-cause this', 'why did X happen', 'look into ticket', or a Kandev watch hands over an investigation ticket. Establish evidence-backed findings for bugs, data oddities and product questions without implementing a fix."
---

# investigate — evidence in, findings out, no code

Owns the full lifecycle of an investigation ticket: claim it, find out what actually happened, post findings the reader can verify in under a minute, hand it back. Works for software bugs, data questions and product/behaviour puzzles alike.

## Iron Laws

Violating the letter of a law is violating the law.

1. **Claim first in ticket mode.** Establish task ownership, then set assignee me and state In Progress before investigating. An ad-hoc question has no ticket lifecycle or external comment.
2. **No writes except the findings comment and the state changes.** No code, no PR, no branch, no config, no new tickets. Suggest follow-ups in the comment; a human creates them.
3. **Every claim carries its evidence or says "not verified".** A record id, a query, a log line, a file:line, a live API response, a screenshot. A claim with none of those is a guess and must be labelled `not verified: <why>`.
4. **Findings are short.** Headline block ≤ 8 lines, whole comment ≤ 300 words before an optional `Detail` section. The reader gets the answer from the headline alone.
5. **Never redo a finished investigation.** If a root-cause comment already exists, verify its claims against current state and post only corrections or `Verified, nothing to add` — one line.

## Red Flags — STOP

- **Reading code before claiming the ticket** → STOP, claim it, then read.
- **Writing "probably", "likely", "I think" without an evidence tag** → STOP, either find the evidence or tag it `not verified`.
- **Comment past 300 words with no `Detail` heading** → STOP, move everything below the fold.
- **Reaching for a code fix "while I'm here"** → STOP, it goes in Fix options.
- **A data source you cannot reach (Honeycomb, prod DB, Sentry)** → STOP hiding it at the bottom; it goes in the headline block as `⚠️ not checked: <source> (<why>)`.
- **Treating a turn ending as completion** → STOP; the handoff needs findings, evidence gaps and the resulting ticket state.

## Rationalizations

| Excuse | Reality |
|---|---|
| I'll move it to In Progress once I know it's real | The label made it real. Claim first. |
| The evidence is obvious from the code | Obvious to you is not provable to the reader. Cite file:line. |
| More detail makes it more convincing | The reader stops at line 9. Detail goes below the fold. |
| Creating the follow-up ticket saves a step | Writes beyond the comment are not yours to make. |
| The prior comment is old, I'll redo it properly | Verify it against current state; post only the delta. |

## Steps

**0. Tools and ownership.** Use the host's native read/search tools. For a ticket, discover Linear issue/comment/user capabilities by function and inspect their actual schemas; unavailable required access blocks ticket lifecycle actions. Reuse an existing Kandev task and its issue binding. If another active task already owns the investigation, resolve ownership before claiming; do not assume a label alone means an active watcher or create another session. Ad-hoc questions skip Linear operations and return findings in the conversation.

**1. Claim.** `get_issue` (with relations). If state is Done/Cancelled: stop and report. Otherwise `save_issue(id, assignee: "me", state: "In Progress")`. If the state name is rejected, report the error and stop. Then `list_comments`; if a root-cause comment exists, switch to Law 5 mode.

**2. Read.** Ticket, every comment, related and parent tickets, linked PRs. Write down, in one line each: the reported symptom, who saw it, when, and the reporter's own theory (kept separate from yours).

**3. Hypotheses before evidence.** List at least three, and at least one from outside the code: user behaviour, upstream data, timing/deploy, config, product expectation mismatch. Rank by cheapest to disprove. Do not start with the one the ticket suggests.

**4. Evidence, cheapest first.** For each hypothesis until one survives:
   - Reproduce or observe the actual record: Avo/admin link, DB row ids, timestamps.
   - Telemetry: Honeycomb trace/query link, Sentry issue, job logs. Record the query, not just the result.
   - Code: `file:line` on the current default branch, plus `git log -S`/blame for when it changed.
   - Upstream: live API response captured today, with the fields that matter.
   - Blast radius: one count query (how many users/records/events), with the query.
   Stop when the surviving hypothesis explains every observation in step 2. If none does, that is the finding.

**5. Return findings.** In ticket mode, post through the available comment tool when the invocation/session authorizes that action, then read it back. Otherwise show the draft and identify posting as outstanding. Ad-hoc investigations return the same structure in the conversation:

```
**<Headline: what happened, one sentence, no jargon>**

**Verdict:** ✅ confirmed | 🟡 likely (what is missing) | ❌ unknown     ← about the mechanism only
**Impact:** <who/how many, one line, with the query or record ids>
**Cause:** <one sentence, with file:line or record id>
⚠️ not checked: <source> (<why>)          ← only when a source you needed was unreachable

| Evidence | Link / id |
|---|---|
| <≤6 rows, one claim each> | <Avo/Honeycomb/PR/file:line/record id> |

**Fix options** (≤3, each: what, effort S/M/L, what it does not cover)
**Not verified:** <claims you could not prove, or "none">

```diff
- <what is broken, one line>
+ <what is safe / already handled, one line>
```

<details><summary>Detail</summary>
<everything else: queries run, full payloads, the disproved hypotheses and why>
</details>
```

Verdict grades the mechanism: ✅ when the cause is proven by file:line, a reproduction or a record; 🟡 when one link in the chain is unproven; ❌ when no hypothesis survived. How often it happens and to whom belongs in **Impact**, and when you could not measure it, Impact says so and the ⚠️ line names the source you lacked.

Before posting: count words above `Detail` (≤ 300), check every row has a link or id, check the ⚠️ line exists if a needed source was unreachable.

**6. Hand back.** In ticket mode, after findings are posted, move to In Review and read back the result. If blocked by access, failed writes or two consecutive tool failures, retain In Progress and report partial findings and the next action; do not manufacture a completed handoff. Ad-hoc work ends with the evidenced answer and limitations. In a signal-gated Kandev step, use the exposed completion tool only after that step's criteria are met and no decision/action remains pending. A missing tool is an explicit handoff gap, not permission to infer success from turn completion. No Fleet command is required.

## Running by hand

Check for active ownership when starting a ticket manually; a work-type label is an intake hint, not proof of a running task. Respect an already-owned Kandev task and existing authorization. Any required question uses Kandev's question facility when present: pending/timeout means stop and wait, not an answer. Do not remove labels or cancel another task merely to proceed.

## When NOT to use

The ticket asks for a change, not an answer (use e2e). The question is answerable from the ticket text alone (answer it, no lifecycle).
