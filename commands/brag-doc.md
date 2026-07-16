---
description: Generate weekly brag doc entries from GitHub activity
---

# Brag Doc Generator

Generate weekly brag doc entries by pulling GitHub activity (merged PRs, reviews given) and synthesizing them into a meaningful accomplishments document. Inspired by [Julia Evans' brag document approach](https://jvns.ca/blog/brag-documents/).

The goal is NOT to produce a prettified git log. It's to capture the **impact and narrative** of your work — what you achieved, why it mattered, and what it took. "You don't have to try to make your work sound better than it is. Just make it sound exactly as good as it is."

## Parameters

Parse from user input:
- **github_username**: GitHub username to pull activity for (default: current user via `gh api user --jq .login`)
- **week**: Week commencing date like "2025-01-06" (default: current week's Monday)
- **repos**: Comma-separated `owner/repo` list (default: discover from `gh repo list --limit 10 --json nameWithOwner --jq '.[].nameWithOwner'`)
- **output**: Output file path (default: `./brag-{week-commencing}.md` in current directory)

## Steps

### 1. Resolve GitHub User

Determine the GitHub username:
- If provided explicitly, use it
- Otherwise run `gh api user --jq .login` to get the authenticated user

### 2. Calculate Week Range

For the given week commencing date (e.g., "2025-01-06"):
- Start: The provided Monday date (YYYY-MM-DD)
- End: Sunday of that week (start + 6 days)

If no week specified, calculate current week's Monday.

### 3. Pull GitHub Data

For each repo in the repos list, run these gh CLI commands:

**Merged PRs by this person:**
```bash
gh pr list --repo {owner/repo} --author {github_username} --state merged --search "merged:{start}..{end}" --json number,title,mergedAt,url,body --limit 50
```

**Reviews given by this person:**
```bash
gh api "repos/{owner/repo}/pulls?state=all&per_page=100" --jq '.[] | select(.updated_at >= "{start}" and .updated_at <= "{end}")' | head -50
```

Then for PRs in that timeframe:
```bash
gh api "repos/{owner/repo}/pulls/{pr_number}/reviews" --jq '.[] | select(.user.login == "{github_username}")'
```

Note: The reviews query is expensive. If it times out or returns too much, summarize what you can get.

**IMPORTANT:** Also fetch the PR body/description for each merged PR — this contains the "why" context that makes the brag doc valuable. Use the `body` field from the PR JSON.

### 4. Analyse and Group

Before writing the document, analyse the raw GitHub data:

1. **Read every PR description** to understand the why, not just the what
2. **Group PRs into projects/themes** — don't just list them chronologically. Look for:
   - PRs that are part of the same feature or initiative
   - Incident response work
   - Infrastructure/platform improvements
   - Refactoring or tech debt reduction
3. **Identify impact** for each group:
   - Quantitative: performance numbers, error reduction percentages, volume changes
   - Qualitative: unblocked a team, improved developer experience, resolved an incident
4. **Note "fuzzy" work** that's easy to undersell: code quality improvements, observability, cleanup, review thoroughness

### 5. Generate Brag Document

Create the markdown file at the output path.

Use this format:

```markdown
---
week_commencing: {YYYY-MM-DD}
week_ending: {YYYY-MM-DD}
github_user: {github_username}
generated: {today}
repos: {repos}
---

# Week of {week-commencing}

## Projects & Impact

{Group related PRs into project themes. For each project:}

### {Project/Theme Name}

{2-3 sentences explaining what this work achieved and WHY it matters. Focus on impact, not implementation details. Include numbers where available (e.g. "reduced error volume by 57%", "cut page load time from 3s to 800ms"). For incident response or reliability work, explain what was at risk.}

{List the PRs that contributed to this project:}
- [#{number}]({url}): {title}
- [#{number}]({url}): {title}

{Repeat for each project/theme}

## Collaboration & Reviews

{Don't just list PRs reviewed. Describe the nature of your review contributions:}
- What areas/teams did you support?
- Any particularly thorough or impactful reviews?
- Did you help onboard or unblock someone?

Reviews given: {For each, one line with PR link and context}

## Design & Technical Decisions

{Capture any significant decisions made this week, even if they seem small:}
- Architecture or approach decisions and the reasoning
- Trade-offs considered
- Things you chose NOT to do and why

## What I Learned

{New technologies, tools, domain knowledge, or insights gained this week}

## What Took Effort

{Work that was harder than it looks from the outside. The "fuzzy" contributions:}
- Debugging sessions, investigation time
- Cross-team coordination
- Navigating legacy code or complex systems
- Making something work that kept breaking

## Raw Activity

<details>
<summary>Full PR list ({merged_count} merged, {review_count} reviews)</summary>

### Merged PRs
{For each PR:}
- [#{number}]({url}): {title} (merged {date})

### Reviews Given
{For each review:}
- [#{pr_number}]({url}): {pr_title} ({review_type})

</details>
```

### Writing Guidelines

When generating content for each section:

- **Lead with impact, not activity.** "Resolved data retention incident affecting N customers" not "Merged 3 PRs for INC-145"
- **Explain the "so what".** Every project section should answer: why should anyone care about this work?
- **Include the follow-up.** Don't just say you shipped something — note adoption, feedback, or next steps if visible from PR discussions
- **Don't undersell reliability/cleanup work.** Frame it in terms of what it prevented or enabled: "Reduced Sentry noise by 60%, making real errors visible again" not "Filtered some errors from Sentry"
- **Be specific with numbers.** Pull percentages, counts, and metrics from PR descriptions wherever available
- **Leave placeholders for things you can't infer.** Mark sections with `<!-- TODO: add context -->` where the person should fill in details only they know (e.g. verbal discussions, pairing sessions, design meetings)

### 6. Confirm Completion

Report:
- File created at: {path}
- PRs found: {count}
- Reviews found: {count}
- Projects identified: {list of theme names}

## Error Handling

- **gh CLI not authenticated**: Tell user to run `gh auth login`
- **No activity found**: Create file with empty sections, note "No GitHub activity found for this period"
- **API rate limited**: Report what was captured, suggest trying again later

## Examples

```
/brag-doc
→ Generates current week for authenticated GitHub user across their recent repos

/brag-doc octocat 2025-03-10 octocat/hello-world
→ Generates week of March 10th for octocat in a specific repo

/brag-doc myuser 2025-01-06 org/repo-a,org/repo-b
→ Generates week of Jan 6th across multiple repos
```
