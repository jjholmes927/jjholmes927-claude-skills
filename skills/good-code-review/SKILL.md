---
name: good-code-review
description: "Use when the user says /good-code-review, 'review against good code', 'check this against my standards', or when /e2e Stage 6 runs its good-code lens. Read-only review of a PR, branch range or commit against Joel's good-code checklist (life-vault), with evidence for every finding."
---

# good-code-review: is this correct and safe to change?

Reviews a change against Joel's good-code checklist. The checklist is never copied into this skill: it lives in life-vault and is read fresh every run, so the standard has exactly one home.

## Iron Laws

1. **Read-only.** Never edit, commit, push, comment on a PR or call a state-changing tool. Output goes back inline to whoever asked.
2. **No checklist, no review.** If the checklist can't be read, say so and stop. Never review from memory of what it probably says.
3. **Every finding carries evidence** a reader can check in under a minute: a file and line, the scenario that goes wrong, and why you believe it.
4. **Try to disprove each finding before reporting it.** If you can't build a concrete scenario, it's a question, not a finding.

## Step 0: Scope

`$ARGUMENTS` is one of:
- a PR reference (`142`, `#142`, or a URL ending `/pull/<n>`): review that PR's diff against its base
- a range (`base...HEAD`): review that branch range
- a commit SHA: review that commit
- empty: review the current branch against its merge base with the default branch

Record the exact head SHA you reviewed. Every finding is about that commit.

## Step 1: Load the checklist

Read, in order, the first that exists:
1. `$GOOD_CODE_CHECKLIST`
2. `~/engineering/life-vault/06-principles/good-code.md`

If neither is readable, output exactly this and stop:

```
good-code-review: checklist unavailable (<path tried>, <reason>). No review performed.
```

The checklist has 13 ranked principles, a "what bad code looks like" symptom table, review questions per principle, and the rules for reviewing against it. When two principles conflict, the higher-ranked one wins. Correctness, security and required behaviour aren't up for trade.

## Step 2: Read the change, then what it touches

1. Read the full diff and every changed file in full, not just the hunks.
2. **Read beyond the diff.** For each changed function, method, field or contract, find its callers and readers with a text search, and open them. Omission bugs (a renamed field still read elsewhere, a caller that now passes the wrong thing) only show up there.
3. Read the repo's own guides if present (`AGENTS.md`, `CLAUDE.md`, contributing docs). A pattern the repo has chosen beats a generic preference (principle 13).

## Step 3: Apply the review questions

Work through the checklist's review questions for every principle that the change actually touches. Skip principles with nothing to say. Pay particular attention to the questions that have caught real bugs:
- **Wiring:** is new code actually called in production, or just tested?
- **Done means done:** is "completed" recorded only once the effect has happened?
- **Running twice:** retries, double clicks, concurrent runs, a crash halfway, a lost response.
- **The last release:** can the new code read what the previous version saved?
- **Trust boundaries:** permissions in the usual place, untrusted input (including model output) checked, secrets and fixtures out of what ships.
- **Failing loudly:** nothing swallowed, and errors report safe ids, the stage and the error class.

Scale rigour to the code: a throwaway script doesn't get the full treatment.

## Step 4: Report

For each finding, one entry:

```
<P1|P2|P3> · #<principle> · <file>:<line>
What happens: <the concrete scenario that goes wrong>
Evidence: <what you read or ran that shows it; mark anything inferred as inferred>
Refutation tried: <what would make this wrong, and why it doesn't apply>
Fix: <the smallest change that resolves it>
```

Severity:
- **P1:** wrong result, data loss, a security hole, or broken for real users. Must fix before ship.
- **P2:** a real defect or a missing test on risky logic. Should fix before ship.
- **P3:** design, naming or simplicity. Fine to defer.

Then a short footer:

```
Reviewed <head SHA> against good-code (<checklist path>) · <N> findings (P1 <n>, P2 <n>, P3 <n>)
Not checked: <anything you couldn't verify, and why>
```

If there's nothing to report, say "No findings" with the same footer. Never say "no findings" when part of the review couldn't run; list that under "Not checked" instead.

**Evidence rules** (from the checklist): say which commit you reviewed; keep observed facts, inferences and unknowns separate; missing evidence is an unknown, not a defect; never report a target as a result; coverage and line counts support judgement, they don't replace it.

## Relationship to other reviews

- **`/e2e` Stage 6** runs this as its good-code lens next to `ponytail-review`. The coordinator merges both lists; this skill doesn't need to know about the other.
- **Beam's `review-pr`** (beam-claude-skills, run in magicnotes CI) is separate and unchanged. This is Joel's personal version while it proves itself.
