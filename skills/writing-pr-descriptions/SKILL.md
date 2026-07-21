---
name: writing-pr-descriptions
description: Use whenever a pull-request description is being written or changed — drafting a PR body (via /ship or ad hoc), tightening an existing description, or checking one against the team format
---

# Writing PR Descriptions

Goal: a reviewer absorbs the description in under 30 seconds and knows what changed, why, and what to watch. Format agreed with the Interpret team (PR-context experiment, Jul 2026), building on the 400-line PR cap.

## Format

```markdown
**What**
Max 3 bullets or 2–3 short sentences: the user-visible capability change, in plain language.

**Why**
Max 3 bullets or 2–3 short sentences: motivation in real-world terms, with real numbers when you have them (latency, cost, error rate, sample sizes).

**Worth noting** (optional — only when there is something)
Steps to reproduce (bug fixes) · deploy notes · deferred follow-ups · verification evidence.
```

## Hard rules

- **Each section caps at 3 bullets or 2–3 sentences.** If it genuinely can't fit, the PR is probably doing too much — flag that instead of writing more.
- **One idea per sentence or bullet.** Never compress five facts into one 70-word sentence to stay under the count — that passes the letter and fails the reader. Three short bullets beat one dense sentence every time.
- **Outcome, not inventory.** Don't list function names, constants, or "wired X into Y" — the diff covers that. Say what the change *causes*.
- **Stacked PRs**: one line at the top — position and where the big picture lives ("2/3, stacked on #8656 — context in #8562"). The story is told once, in the first PR, not repeated per layer.
- **No "Fixes TICKET-ID" footer.** The ticket goes in the title bracket (`[INT-350]`) — Linear attaches via the title. Linking it inline in Why is fine when it adds context.
- **Bug fixes** get Steps to Reproduce in the Worth-noting section.
- **Never add Claude/AI attribution.**
- Whole body ≤ ~10 lines, before any bot-appended content.

## Example (a real one that works)

```markdown
**What**
Two changes to what reaches #interpret-new-conversations: feedback now always posts (beam-org included, any rating), and saved-conversation messages post for all phone calls. Beam in-person saved messages stay suppressed.

**Why**
Phone-call interpret is early and beam dogfooding is where most early feedback and usage comes from — suppressing it hid exactly the signal we want to watch.
```

## Counter-examples

- **The mega-sentence** — "`Turns::RescueUnrecognisedTurns` (PR 2 of 3): when LLM detect returns 'none' for a turn and the conversation has exactly one non-English language, re-transcribe that segment's buffered audio with the language as a Scribe hint and swap in the retry only if it passes default-reject validation — word-logprob confidence floor plus an independent LLM detect agreeing…" — technically two sentences, unreadable. Break it: what triggers it · what it does · what gates it.
- **The inventory** — a bullet per code change ("Add `Foo::Bar.baz`", "Wire it into `Some::Service`", "Add `THING_CONSTANT`…") is a worse version of the diff.
