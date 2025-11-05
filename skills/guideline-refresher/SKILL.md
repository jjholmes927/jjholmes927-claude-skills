---
name: guideline-refresher
description: Use when coding guidelines are outdated or need updating - automatically analyzes git history, PR reviews, and approved patterns to refresh area-specific guidelines based on actual codebase evolution
---

<EXTREMELY-IMPORTANT>
This skill MUST be used when:
1. User mentions guidelines being "out of date" or "stale"
2. Major migration or refactoring has occurred (e.g., frontend framework migration)
3. User wants to update .claude or .cursorrules based on recent changes
4. Team patterns have evolved but documentation hasn't
5. You need to understand what "good" looks like for a specific area

This is NOT optional. If guidelines are stale, manual updates will miss patterns. This skill extracts truth from the codebase.
</EXTREMELY-IMPORTANT>

# Guideline Refresher Skill

## Purpose
Automatically analyze recent code changes, PR reviews, and commit patterns to refresh coding guidelines for specific areas of a codebase. Captures what the team actually approves, not what they think they do.

## When to Use This Skill

Use this skill when:
- Guidelines feel outdated after a migration or major refactor
- New patterns have emerged but aren't documented
- You need area-specific rules (frontend, backend, utils, etc.)
- PR reviews repeatedly mention the same issues
- You want evidence-based guidelines, not assumptions

## How This Skill Works

This skill analyzes multiple data sources to understand what "good code" means in your project:

1. **Git History Analysis**: Extracts patterns from commit messages, identifies refactoring themes, tracks technology adoption
2. **PR Review Mining**: Analyzes merged PR review comments to identify recurring feedback themes (testing, types, performance, organization)
3. **File Pattern Analysis**: Examines file organization, naming conventions, and technology usage
4. **Guideline Generation**: Creates evidence-based guidelines with specific recommendations
5. **Change Detection**: Compares with existing guidelines to highlight what changed and why

## Usage

### Basic Invocation
```bash
# Analyze and refresh guidelines for a specific area
refresh-guidelines --area="frontend/components" --depth=standard

# Quick refresh (last 30 days, 20 PRs)
refresh-guidelines --area="api/services" --depth=quick

# Deep analysis (last 180 days, 100 PRs)
refresh-guidelines --area="utils/helpers" --depth=deep
```

### From Claude Code
When user requests guideline refresh, follow this process:

1. **Identify the Area**: Ask user which area needs refresh if not specified
   - Examples: "frontend/components", "backend/api", "utils", "services"

2. **Choose Depth**:
   - `quick`: Fast scan, recent changes only (30 days, 20 PRs)
   - `standard`: Balanced analysis (90 days, 50 PRs) - DEFAULT
   - `deep`: Comprehensive review (180 days, 100 PRs)

3. **Run Analysis**: Execute the refresh_guidelines.py script

4. **Review Output**: Analyze the generated guidelines and report

5. **Enhance Guidelines**: Add code examples, validate recommendations, identify conflicts

6. **Save Results**: Commit updated guidelines to .claude/guidelines/

## Step-by-Step Process

### Phase 1: Analysis
```bash
# Run the core analysis
python3 skills/guideline-refresher/refresh_guidelines.py \
  --area "frontend/components" \
  --depth standard
```

This will:
- Scan git history for the area
- Extract PR review comments
- Analyze file patterns and naming conventions
- Generate metrics and findings

### Phase 2: Generation
The script automatically:
- Loads current guidelines (if they exist)
- Generates updated guidelines based on findings
- Compares old vs new to highlight changes
- Saves to `.claude/guidelines/{area}.md`
- Creates analysis report in `.claude/reports/`

### Phase 3: Review & Enhancement
As Claude Code, you should:

1. **Read the generated guidelines**:
   ```
   Read .claude/guidelines/{area}.md
   ```

2. **Read the analysis report**:
   ```
   Read .claude/reports/guideline-refresh-{timestamp}.md
   ```

3. **Validate recommendations**:
   - Do they align with broader project standards?
   - Are there contradictions with other areas?
   - Are the metrics meaningful?

4. **Add code examples**:
   - Find good examples from recent merged PRs
   - Show before/after for refactoring patterns
   - Demonstrate recommended practices

5. **Fill gaps**:
   - Add testing requirements if not covered
   - Include accessibility/security if relevant
   - Link to related documentation

## Configuration

### config.json Structure
```json
{
  "analysis_depth": {
    "quick": {
      "pr_limit": 20,
      "commit_days": 30,
      "min_pattern_frequency": 3
    },
    "standard": {
      "pr_limit": 50,
      "commit_days": 90,
      "min_pattern_frequency": 5
    },
    "deep": {
      "pr_limit": 100,
      "commit_days": 180,
      "min_pattern_frequency": 3
    }
  },
  "output_format": {
    "guidelines_file": ".claude/guidelines/{area}.md",
    "report_file": ".claude/reports/guideline-refresh-{date}.md",
    "backup_previous": true
  }
}
```

### Area-Specific Configs (Optional)
Create `.claude/area-configs/{area}.json` for custom analysis:

```json
{
  "patterns_to_track": [
    "component composition",
    "state management",
    "performance optimization"
  ],
  "required_sections": [
    "Component Structure",
    "Props Interface",
    "Testing Requirements"
  ],
  "reviewers_to_weight": {
    "senior-dev": 2.0,
    "tech-lead": 2.5
  }
}
```

## Output Structure

After running this skill, your repo will have:

```
.claude/
├── guidelines/
│   ├── frontend_components.md      # Area-specific guidelines
│   ├── backend_api.md
│   └── utils_helpers.md
├── reports/
│   ├── guideline-refresh-20250105_143022.md  # Analysis reports
│   └── guideline-refresh-20250112_091544.md
└── area-configs/                    # Optional custom configs
    └── frontend-components.json
```

## Example Workflow

### Scenario: Frontend Migration
User: "We migrated from Vue to React 3 months ago. Our .claude guidelines still mention Vue patterns. Can you update them?"

**Your Response:**
1. "I'll use the guideline-refresher skill to analyze your React patterns from the last 3 months."

2. Run analysis:
   ```bash
   python3 skills/guideline-refresher/refresh_guidelines.py \
     --area "frontend/components" \
     --depth standard
   ```

3. Review generated guidelines in `.claude/guidelines/frontend_components.md`

4. Read analysis report to understand findings

5. Enhance guidelines with:
   - React-specific patterns found in merged PRs
   - Hook usage patterns
   - Component composition examples
   - Testing patterns with React Testing Library

6. Remove outdated Vue references

7. Save and commit updated guidelines

### Scenario: API Guidelines
User: "Create coding guidelines for our API services based on what we've actually been doing."

**Your Response:**
1. "I'll analyze your API service history to extract actual patterns."

2. Run analysis:
   ```bash
   python3 skills/guideline-refresher/refresh_guidelines.py \
     --area "backend/api" \
     --depth deep
   ```

3. Review findings:
   - Error handling patterns
   - Validation approaches
   - Authentication/authorization patterns
   - API versioning strategy

4. Generate comprehensive guidelines with examples from the codebase

5. Include common PR review feedback (e.g., "Always validate input", "Use proper status codes")

## Critical Rules

### 1. Evidence-Based Only
NEVER make up guidelines. Base everything on:
- Actual commit messages
- Merged PR review comments
- File patterns in the codebase
- Frequency of patterns (min_pattern_frequency)

### 2. Area-Specific
Different areas evolve differently:
- Frontend might adopt new hooks patterns
- Backend might enforce new validation rules
- Utils might standardize error handling

Keep guidelines scoped to the area being analyzed.

### 3. Compare and Contrast
Always compare new guidelines with old:
- What changed? Why?
- What was removed? Still relevant?
- What was added? From which PRs?

### 4. Backup Everything
The script backs up previous guidelines automatically:
- `frontend_components.md` → `frontend_components.20250105_143022.md.bak`
- Never lose history

### 5. Review Before Accepting
Don't blindly accept generated guidelines:
- Validate metrics make sense
- Check recommendations align with project values
- Ensure code examples are good examples
- Look for contradictions

## Common Pitfalls

### Pitfall 1: Not Reading the Report
The analysis report contains WHY guidelines changed. Read it.

**Wrong:**
```
"Guidelines updated based on recent changes."
```

**Right:**
```
"Guidelines updated based on:
- 47 commits mentioning React hooks
- 12 PR reviews emphasizing prop validation
- TypeScript strict mode adopted across 23 files
See full report: .claude/reports/guideline-refresh-20250105_143022.md"
```

### Pitfall 2: Too Broad Area
Analyzing entire "frontend" is too broad. Be specific:
- ✅ "frontend/components"
- ✅ "frontend/pages"
- ✅ "frontend/hooks"
- ❌ "frontend" (too broad)

### Pitfall 3: Ignoring Review Themes
If testing mentioned in 15 PR reviews, that's critical:
```markdown
## Testing Requirements
**Based on 15 PR reviews emphasizing testing:**
- All components must have unit tests
- Integration tests for API interactions
- Minimum 80% coverage for new code
```

### Pitfall 4: Not Adding Examples
Generated guidelines are evidence-based but lack examples:

**Generated:**
```markdown
- Use TypeScript strict mode
```

**Enhanced by You:**
```markdown
- Use TypeScript strict mode
  ```typescript
  // Good: Explicit types, null checks
  interface UserProps {
    user: User | null;
    onUpdate: (user: User) => void;
  }

  // Bad: Any types, no null handling
  function updateUser(user: any) { ... }
  ```
```

## Integration with CI/CD

### Automated Refresh (Optional)
Create `.github/workflows/refresh-guidelines.yml`:

```yaml
name: Refresh Guidelines
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Refresh Frontend Guidelines
        run: |
          python3 skills/guideline-refresher/refresh_guidelines.py \
            --area "frontend/components" \
            --depth standard

      - name: Create PR
        uses: peter-evans/create-pull-request@v5
        with:
          title: "Auto-refresh: Updated frontend guidelines"
          body: "Automated guidelines refresh based on recent code changes"
          branch: "auto-refresh-guidelines"
```

## Customization

### Custom Analyzers
Extend `refresh_guidelines.py` with domain-specific analyzers:

```python
def analyze_api_contracts(self):
    """Analyze API endpoint consistency"""
    # Your custom logic
    pass

def analyze_security_patterns(self):
    """Extract security-related patterns"""
    # Your custom logic
    pass
```

### Custom Review Themes
Add to `refresh_guidelines.py`:

```python
# Add custom themes to track
custom_themes = {
    'accessibility': ['a11y', 'aria', 'screen reader', 'keyboard nav'],
    'performance': ['lazy load', 'memoize', 'optimize', 'bundle size'],
    'security': ['sanitize', 'xss', 'csrf', 'injection']
}
```

## Success Criteria

You've successfully used this skill when:

✅ Guidelines are generated from actual codebase data
✅ Analysis report shows meaningful metrics (commits, PRs, patterns)
✅ New guidelines differ from old in specific, evidence-based ways
✅ Code examples demonstrate recommended patterns
✅ Recommendations align with PR review feedback
✅ Team can see WHY guidelines changed (report + backup)
✅ Guidelines are actionable (specific, not vague)

## Failure Modes

🚫 Generated guidelines are generic/vague
🚫 No analysis report produced
🚫 Metrics are zero or nonsensical
🚫 Guidelines unchanged despite major codebase evolution
🚫 No code examples provided
🚫 Recommendations contradict recent merged code
🚫 Previous guidelines lost (no backup)

## Questions to Ask

Before running this skill:
- What area needs refresh? (be specific)
- How far back should we analyze? (depth: quick/standard/deep)
- Are there existing guidelines to compare against?
- Are there area-specific patterns to track?

After running this skill:
- Do the metrics make sense for this area?
- What are the top 3 changes from old guidelines?
- Which PRs drove these changes?
- Are there contradictions with other areas?
- Do we need code examples for clarity?

## Summary

This skill automates the tedious process of keeping guidelines current by:
1. Mining your git history for actual patterns
2. Extracting team preferences from PR reviews
3. Analyzing file organization and naming
4. Generating evidence-based guidelines
5. Tracking changes over time

Use it whenever guidelines feel stale or after major code evolution. Trust the data, but review and enhance the output with code examples and context.
