---
name: codex-collab
description: "Use when the user says /codex-collab or asks for a second opinion, cross-model check, corroboration, sanity check, or an extra pair of eyes from the Codex CLI on current work — a finding, conclusion, plan, design, diff, or analysis — alongside whatever skill or workflow is already running."
---

# codex-collab — an independent Codex consultation

Wrapper script: `${CLAUDE_PLUGIN_ROOT}/skills/codex-collab/scripts/collab-codex.sh`
(`ask <workdir> <effort> <prompt-file>` → prints `thread_id: <id>` then the reviewer's reply; `resume <workdir> <thread-id> <effort> <prompt-file>` for follow-ups in the same session; `review <workdir> [--commit <sha>|--base <branch>|--uncommitted]` runs codex's native reviewer.)

Before the first call, select `CODEX_COLLAB_MODEL` explicitly from the task profile or the user's configured Codex model. Record requested and observed identity separately; fresh context does not imply a different model. Missing resolved identity stays unknown. Then set `CODEX_COLLAB_DIR` to a subdir of your session scratchpad and write prompt files there too — nothing lands in the repo. Never hand-roll `codex exec` invocations or interpolate prompts with `"$(cat ...)"`; the wrapper handles flags, stdin, logging, and thread-id capture.

## What this is

A short read-only consultation with the reviewer (codex) that composes with any running workflow — debugging, planning, reviewing, investigating. the reviewer inspects the repo and gives judgement; it never writes code here (implementation pipelines are /e2e). When the consultation ends, hand control straight back to the interrupted workflow.

## Iron Laws

Violating the letter of a law is violating the law — there is no spirit-of-the-law exception.

1. **the reviewer never writes to the tree** — every call runs in a read-only sandbox; never "upgrade" to workspace-write.
2. **Blind first** — for second opinions, the reviewer states its own view before hearing yours; reveal your position only in a `resume`.
3. **Disagreement is reported, never silently dropped** — unresolved splits go to the user labeled as such.

## Modes — pick by the ask

| Ask looks like | Mode | How |
|---|---|---|
| "have the reviewer review this too" | review | `review` with the right scope flag |
| "check my conclusion", "poke holes in this" | corroborate | Prompt = evidence + claim + "Try to REFUTE this. First line: CONFIRMED / REFUTED / UNCERTAIN, then reasons with file:line evidence." |
| "what would the reviewer do", "second opinion on the design" | second-opinion | Prompt = context + open question, WITHOUT your answer. After the reply, `resume` with your position and ask the reviewer to reconcile. |

When a review needs plan or conversation context codex's native reviewer can't see, use `ask` with the diff refs instead of `review`.

## Effort

The wrapper always takes effort as its required positional argument (`ask <workdir> <effort> <prompt-file>`) — there is no `--effort` wrapper flag. If the user passed `--effort low|medium|high|xhigh` in the /codex-collab invocation, use that value. Otherwise grade by the question's complexity, not the host task's importance:

| Question shape | Effort |
|---|---|
| Sanity check, single file, mechanical | low |
| Routine review or judgement, clear context | medium |
| Cross-cutting design, multi-file reasoning | high |
| Algorithmic, subtle correctness, security | xhigh |

## Procedure

1. Write the prompt to `$CODEX_COLLAB_DIR/ask-N.md`. the reviewer has NO conversation context: include the task background, exact file paths / shas / line refs, the specific question, and a required output format with the verdict line first.
2. Run `ask` (or `review`); note the `thread_id` for follow-ups. Only `ask` threads are resumable — `review` prints findings with no session to resume.
3. Verify before believing: read the file:line evidence the reviewer cites yourself — the reviewer hallucinates citations too.
4. Arbitrate: label each substantive point `[both]` / `[coordinator-only]` / `[reviewer-only]` by whether your own view agrees.
5. Report to the user: verdict first, then agreements, disagreements with your resolution (or an honest "unresolved"), and the thread id.

## Failure policy

Non-zero exit or empty reply → retry ONCE with the stderr tail appended to the prompt. Second failure → report unavailable, never fake or paraphrase a consultation. An optional opinion may return control to its host workflow; a required review stage remains incomplete and cannot silently downgrade to self-review.

## Rationalizations

| Excuse | Reality |
|--------|---------|
| Faster to just tell the reviewer my conclusion up front | That poisons the second opinion — blind first, reveal only in `resume` |
| the reviewer clearly agrees, no need to check its citations | the reviewer hallucinates file:line too — verify before reporting agreement |
| the reviewer was unavailable, I'll paraphrase what it'd probably say | Never fabricate a consultation; report unavailable and continue |
| I'll upgrade to workspace-write just this once | Read-only is absolute; implementation goes through /e2e |

## Red Flags — STOP

- Running `codex exec` directly instead of the wrapper
- Telling the reviewer your conclusion in a second-opinion first prompt
- Reporting "the reviewer agreed" without reading its cited evidence
- Letting the consultation stall or replace the host workflow

## When NOT to use

Full implementation pipelines (use /e2e); questions you can settle by reading the code yourself in under a minute.
