---
name: skill-reviewer
description: Use when a Claude Code skill or command has been created or edited and needs a quality review, or when checking a skill against current Anthropic/superpowers authoring best practices.
---

# Skill Reviewer

Review a Claude Code skill by dispatching two parallel subagents — one for structural quality against superpowers/Anthropic patterns, one for domain-specific accuracy.

**Core principle: A skill is only as good as its worst instruction. One ambiguous line can cause Claude to take a shortcut that undoes everything else.**

## Parameters

Parse from user input or context:
- **skill_path** (required) — Path to the file to review: a skill's SKILL.md or a command's .md file. If not provided, ask the user.
- **domain** (optional) — Brief description of the skill's domain (e.g., "Sentry error monitoring", "Capybara testing"). If not provided, infer from the skill content.

## Steps

### 1. Read the skill

Read the full file at the given path — a skill's SKILL.md or a command's .md. If there are companion files (references, scripts, examples), note them but focus the review on the main file.

### 2. Dispatch two parallel subagents

Launch both simultaneously using the Task tool with `subagent_type='general-purpose'`.

#### Subagent A: Structural review

Prompt (fill in `[SKILL_PATH]` and `[SKILL_CONTENT]`):

```
You are reviewing a Claude Code skill for quality. Compare it against
the best skill-writing patterns and produce prioritized, actionable feedback.

## Skill under review

Path: [SKILL_PATH]

Content:
---
[SKILL_CONTENT]
---

## Review process

1. Read these reference skills to extract current patterns (read ALL of them):

   Superpowers skills (gold standard for structure and prompt engineering):
   - Glob for all SKILL.md files under the superpowers plugin cache:
     ~/.claude/plugins/cache/superpowers-marketplace/superpowers/*/skills/*/SKILL.md
   - Prioritise reading: systematic-debugging, verification-before-completion,
     writing-skills, brainstorming

   Official Anthropic guides:
   - Fetch https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
     (if the fetch fails, web-search "Anthropic agent skills best practices")
   - ~/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/skills/skill-creator/SKILL.md
   - ~/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/skill-development/SKILL.md

   If the fetched docs contradict the criteria below, the fetched docs win — note
   the discrepancy in your review so the reviewer command can be updated.

2. Evaluate against these criteria:

   FRONTMATTER
   - Is it a skill (name + description in SKILL.md) or command (description only in .md)?
   - name: max 64 chars; lowercase letters, numbers, hyphens only; no XML tags;
     no reserved words ("anthropic", "claude"); gerund form preferred (processing-pdfs)
   - Description: third person; what the skill does AND when to use it, with specific
     trigger phrases — NOT a workflow summary (agents follow the summary instead of
     reading the body)
   - Max 1024 chars for description
   - allowed-tools: listed if the skill uses MCP or restricted tools

   STRUCTURE
   - Core principle / Iron Law statement near the top
   - When to Use / When NOT to Use sections (skills) or Parameters section (commands)
   - Clear step-by-step workflow; copyable checklist for complex multi-step flows
   - Feedback loops where output quality matters (run validator → fix → repeat)
   - Red Flags — STOP section for critical guardrails (if the skill takes actions)
   - Common Rationalizations table (if the skill enforces discipline)
   - Error handling for tool failures

   DEGREES OF FREEDOM
   - Specificity matches fragility: fragile or must-be-sequenced operations get exact
     commands with "do not modify" (low freedom); context-dependent judgment gets
     heuristics (high freedom)
   - One default approach with an escape hatch, not a menu of alternatives

   PROMPT ENGINEERING
   - <EXTREMELY-IMPORTANT> tags for critical rules
   - Emphasis markers preventing Claude from skimming past guardrails
   - Decision trees for complex classification logic
   - Concrete input/output examples where output style matters

   CONTENT
   - Concise: assumes Claude is smart; every paragraph justifies its token cost
   - Consistent terminology (one term per concept, used throughout)
   - No time-sensitive information (deprecated details go in an "old patterns" section)
   - Forward-slash paths only, never Windows-style

   TOKEN EFFICIENCY & PROGRESSIVE DISCLOSURE
   - SKILL.md body under 500 lines (commands more flexible); split into reference
     files when approaching the limit
   - Reference files linked ONE level deep from SKILL.md (nested references get
     partially read); files >100 lines start with a table of contents
   - Progressive disclosure (metadata → body → references)

   TOOL USAGE (if applicable)
   - Correct tool names and parameter formats
   - MCP tools referenced by fully qualified name (ServerName:tool_name)
   - ToolSearch step for deferred/MCP tools
   - Dependencies stated explicitly, never assumed installed
   - Fallback guidance for failures

   BUNDLED SCRIPTS (if the skill ships code)
   - Scripts handle their own error conditions rather than deferring to Claude
   - No unexplained constants (timeouts, retry counts need justification)
   - Instructions say whether each script is executed or read as reference
   - Plan-validate-execute pattern for batch or destructive operations

   SAFETY (if the skill takes actions)
   - Confirmation before destructive/irreversible actions
   - Undo guidance

   OUTPUT FORMAT (if the skill produces output)
   - Structured, actionable, includes links where appropriate

   TESTING
   - Evidence the skill was tested against real scenarios (evaluations, baseline
     runs); flag as a gap if there is none

3. Return your review as:

   ### Priority 1: Critical (significantly impacts reliability)
   [numbered items with specific suggestions]

   ### Priority 2: Important (improves quality)
   [numbered items]

   ### Priority 3: Nice to have (polish)
   [numbered items]
```

#### Subagent B: Domain research

Prompt (fill in `[SKILL_NAME]`, `[SKILL_DOMAIN]`, and `[SKILL_CONTENT]`):

```
You are a domain expert reviewing whether a Claude Code skill's technical
content is accurate and follows best practices for its domain.

## Skill under review

Name: [SKILL_NAME]
Domain: [SKILL_DOMAIN]

Content:
---
[SKILL_CONTENT]
---

## Review process

1. Search the web for current best practices in this domain:
   - Official documentation for tools/services the skill interacts with
   - Industry best practices for the workflow being automated
   - Common pitfalls and anti-patterns
   - Recent changes or updates (search with current year)

2. Read codebase files the skill references to verify:
   - File paths actually exist
   - Code patterns described match reality
   - Configuration details are accurate
   - Tool parameters and API details are correct

3. Evaluate:

   ACCURACY
   - Are technical details correct?
   - Are tool/API parameters accurate?
   - Are heuristics/rules sound?

   COMPLETENESS
   - Important domain best practices the skill misses?
   - Common pitfalls not addressed?
   - Newer/better approaches available?

   SAFETY IN CONTEXT
   - Could the skill's actions cause problems in this domain?
   - Are guardrails appropriate for the domain's risk level?
   - Is the automation level appropriate?

4. Return your review as:

   ### Domain accuracy issues
   [specific inaccuracies or outdated information]

   ### Missing best practices
   [domain practices the skill should incorporate]

   ### Domain-specific improvements
   [suggestions requiring domain knowledge]

   ### Verified as correct
   [what you confirmed is accurate]
```

### 3. Synthesise findings

After both subagents return, combine into a single review:

```markdown
## Skill Review: [skill-name]

### Overall assessment
[1-2 sentences: ready to use, needs minor fixes, or needs significant rework]

### Critical fixes (do before using)
[Combined P1 items from both subagents]

### Important improvements
[Combined P2 items]

### Polish
[Combined P3 items]

### Domain validation
[Summary of what was confirmed correct and what needs fixing]

### Recommended next steps
1. [specific action]
2. [specific action]
```

### 4. Apply fixes

Ask the user which items to fix. Apply in priority order (Critical first).

After applying fixes, re-read the skill for a quick sanity check. Do not re-run the full review unless the user asks.

## Examples

```
/joel-workflow:skill-reviewer .claude/skills/my-skill/SKILL.md
→ Reviews my-skill with its subject area as the domain

/joel-workflow:skill-reviewer skills/brag-doc/SKILL.md
→ Reviews a command file against the command-specific criteria

/joel-workflow:skill-reviewer
→ Prompts for which skill to review
```

## Tips

- For skills interacting with external services (Sentry, Linear, CI), the domain subagent is especially valuable — catches API changes and best practice evolution
- For pure-process skills (TDD, debugging), the structural review matters more
- If a skill is very short (< 200 words), the domain subagent may not be needed — skip it
- The structural subagent reads superpowers skills fresh each time to pick up pattern updates
