# Guideline Refresher Skill

A Claude Code skill that automatically analyzes your codebase evolution and refreshes coding guidelines based on actual patterns, PR reviews, and approved code.

## Problem

Coding guidelines get stale. After migrations, refactorings, or as team patterns evolve, documented guidelines fall out of sync with reality. Manually updating them is tedious and often misses important patterns that emerge organically.

## Solution

This skill automatically:
- Analyzes git history to extract commit patterns and technology adoption
- Mines PR review comments to identify recurring feedback themes
- Examines file organization and naming conventions
- Generates evidence-based guidelines with specific recommendations
- Tracks changes from previous guidelines

## Installation

### For This Plugin Repository

If you're working with this repo as a Claude Code plugin, the skill is already installed in `skills/guideline-refresher/`.

### For Personal Use in Other Projects

Copy the skill to your Claude skills directory:

```bash
# Copy skill to Claude skills directory
mkdir -p ~/.claude/skills
cp -r skills/guideline-refresher ~/.claude/skills/

# Or create a symlink for easier development
ln -s "$(pwd)/skills/guideline-refresher" ~/.claude/skills/guideline-refresher
```

### As a Standalone Tool

You can also use the refresh script directly without Claude Code:

```bash
# Run from anywhere in your project
/path/to/skills/guideline-refresher/refresh.sh --area frontend/components --depth standard
```

## Requirements

- **Python 3.7+** - For running the analysis script
- **git** - For analyzing commit history (always available in repos)
- **gh CLI** (optional but recommended) - For analyzing PR reviews
  ```bash
  # Install gh CLI
  brew install gh  # macOS
  # or visit: https://cli.github.com/

  # Authenticate
  gh auth login
  ```

Without `gh` CLI, the skill will skip PR analysis but still analyze git history and file patterns.

## Usage

### Quick Start

```bash
# Analyze frontend components (standard depth)
./skills/guideline-refresher/refresh.sh --area frontend/components

# Quick analysis of API services (last 30 days)
./skills/guideline-refresher/refresh.sh --area backend/api --depth quick

# Deep analysis of utilities (last 6 months)
./skills/guideline-refresher/refresh.sh --area utils/helpers --depth deep
```

### Direct Python Usage

```bash
python3 skills/guideline-refresher/refresh_guidelines.py \
  --area frontend/components \
  --depth standard
```

### From Claude Code

When chatting with Claude Code, simply say:

> "Refresh guidelines for frontend/components"

Claude will automatically use this skill to analyze your codebase and generate updated guidelines.

## Analysis Depths

Choose the right depth for your needs:

| Depth | Timeframe | PRs Analyzed | Best For |
|-------|-----------|--------------|----------|
| **quick** | 30 days | 20 PRs | Recent changes, quick checks |
| **standard** | 90 days | 50 PRs | Regular updates, balanced view |
| **deep** | 180 days | 100 PRs | Major migrations, comprehensive review |

## What Gets Analyzed

### 1. Git History
- Commit messages and patterns
- Refactoring activity (keywords: refactor, improve, migrate, modernize)
- Technology adoption (TypeScript, React, testing frameworks)
- Frequency of specific patterns

### 2. PR Reviews (requires gh CLI)
- Review comment themes:
  - Code organization
  - Type safety
  - Testing requirements
  - Performance considerations
  - Error handling
  - Naming conventions
  - Documentation
  - Accessibility
  - Security

### 3. File Patterns
- File type distribution (`.ts`, `.tsx`, `.js`, etc.)
- Naming conventions (PascalCase, camelCase, kebab-case, snake_case)
- Directory structure
- File organization patterns

## Output

After running, you'll get two files:

### 1. Guidelines: `.claude/guidelines/{area}.md`

Evidence-based guidelines including:
- Analysis summary with metrics
- Technology focus (based on commits)
- File organization patterns
- Naming convention recommendations
- Code review focus areas
- Recent evolution/refactoring themes
- Specific recommendations
- Changes from previous guidelines

### 2. Report: `.claude/reports/guideline-refresh-{timestamp}.md`

Detailed analysis report with:
- Complete metrics breakdown
- Key findings by category
- Sample review feedback
- Refactoring activity summary
- Next steps checklist

## Example Output

```
.claude/
├── guidelines/
│   ├── frontend_components.md          ← Generated guidelines
│   ├── frontend_components.20250105.md.bak  ← Backup of previous
│   └── backend_api.md
└── reports/
    ├── guideline-refresh-20250105_143022.md  ← Analysis report
    └── guideline-refresh-20250112_091544.md
```

## Configuration

### Global Config: `config.json`

The default configuration is in `config.json`. You can customize:

- Analysis depths (days to analyze, PR limits)
- Review themes to track
- Technology keywords to detect
- Output file locations
- Backup behavior

### Area-Specific Config (Optional)

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

## Examples

### Example 1: Frontend Migration

**Scenario:** Migrated from Vue to React 3 months ago, guidelines still mention Vue.

```bash
# Analyze frontend components over last quarter
./skills/guideline-refresher/refresh.sh \
  --area frontend/components \
  --depth standard
```

**Result:**
- Detects React/hooks mentions in commits
- Extracts component patterns from PR reviews
- Identifies TypeScript adoption
- Generates React-specific guidelines
- Notes removal of Vue patterns

### Example 2: API Standardization

**Scenario:** Want to document actual API patterns for new developers.

```bash
# Deep analysis of API services
./skills/guideline-refresher/refresh.sh \
  --area backend/api \
  --depth deep
```

**Result:**
- Extracts error handling patterns
- Identifies validation approaches
- Documents authentication/authorization patterns
- Captures API versioning strategy
- Includes common PR feedback

### Example 3: Quick Check After Sprint

**Scenario:** Just finished 2-week sprint, want to see if patterns changed.

```bash
# Quick refresh of utils
./skills/guideline-refresher/refresh.sh \
  --area utils \
  --depth quick
```

**Result:**
- Fast scan of last 30 days
- Highlights recent changes
- Updates guidelines if significant patterns emerged

## Workflow Integration

### Manual Workflow

1. **Run Analysis**
   ```bash
   ./skills/guideline-refresher/refresh.sh --area frontend/components
   ```

2. **Review Output**
   - Read generated guidelines: `.claude/guidelines/frontend_components.md`
   - Check analysis report: `.claude/reports/guideline-refresh-*.md`

3. **Enhance Guidelines**
   - Add code examples from recent merged PRs
   - Include project-specific context
   - Link to related documentation

4. **Commit Changes**
   ```bash
   git add .claude/guidelines/frontend_components.md
   git commit -m "docs: refresh frontend component guidelines"
   ```

### Automated Workflow (CI/CD)

Create `.github/workflows/refresh-guidelines.yml`:

```yaml
name: Refresh Guidelines
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:      # Manual trigger

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for analysis

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup gh CLI
        run: |
          type -p gh || (sudo apt-get update && sudo apt-get install -y gh)

      - name: Refresh Frontend Guidelines
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python3 skills/guideline-refresher/refresh_guidelines.py \
            --area frontend/components \
            --depth standard

      - name: Refresh Backend Guidelines
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python3 skills/guideline-refresher/refresh_guidelines.py \
            --area backend/api \
            --depth standard

      - name: Create PR
        uses: peter-evans/create-pull-request@v5
        with:
          title: "docs: auto-refresh coding guidelines"
          body: |
            Automated guidelines refresh based on recent code changes.

            ## Changes
            - Updated frontend/components guidelines
            - Updated backend/api guidelines

            ## Review
            Please review the generated guidelines and add code examples where helpful.
          branch: auto-refresh-guidelines
          commit-message: "docs: auto-refresh coding guidelines"
```

### Pre-Push Hook (Optional)

Refresh guidelines before pushing:

```bash
# .git/hooks/pre-push
#!/bin/bash

CHANGED_AREAS=$(git diff --name-only origin/main...HEAD | cut -d'/' -f1-2 | sort -u)

for area in $CHANGED_AREAS; do
    if [ -d "$area" ]; then
        echo "Checking guidelines for: $area"
        ./skills/guideline-refresher/refresh.sh --area "$area" --depth quick
    fi
done
```

## Best Practices

### 1. Be Specific with Areas

✅ Good:
- `frontend/components`
- `backend/api/services`
- `utils/helpers`

❌ Too Broad:
- `frontend` (too general)
- `src` (entire codebase)
- `.` (everything)

### 2. Choose Appropriate Depth

- **quick**: After sprints, for active areas
- **standard**: Regular updates, balanced coverage
- **deep**: After migrations, major refactors

### 3. Review Before Accepting

Always review the generated guidelines:
- Do metrics make sense?
- Are recommendations aligned with project values?
- Are there contradictions with other areas?
- Do you need to add code examples?

### 4. Add Code Examples

Generated guidelines are evidence-based but lack examples. Enhance them:

```markdown
## Component Structure

**Pattern:** Functional components with hooks (47 commits)

### Example
\`\`\`typescript
// Good: Functional component with TypeScript
interface UserCardProps {
  user: User;
  onEdit: (user: User) => void;
}

export function UserCard({ user, onEdit }: UserCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  // ...
}
\`\`\`
```

### 5. Keep Guidelines Focused

One area = one guideline file. Don't mix concerns:
- Frontend components ≠ backend services
- API endpoints ≠ database schemas
- Utils ≠ configuration

### 6. Schedule Regular Refreshes

Set a cadence:
- **Weekly**: Fast-moving areas
- **Monthly**: Standard areas
- **Quarterly**: Stable areas

### 7. Backup is Automatic

Previous guidelines are backed up as `.bak` files. You can always revert:

```bash
# Restore previous version
cp .claude/guidelines/frontend_components.20250105.md.bak \
   .claude/guidelines/frontend_components.md
```

## Troubleshooting

### "gh CLI not found"

PR analysis requires GitHub CLI:

```bash
# Install
brew install gh  # macOS
# or visit: https://cli.github.com/

# Authenticate
gh auth login
```

Without `gh`, the skill still works but skips PR review analysis.

### "Not in a git repository"

The skill requires a git repository:

```bash
# Initialize git if needed
git init
```

### "Area does not exist"

Check the area path:

```bash
# List directories
ls -la frontend/

# Verify path exists
./skills/guideline-refresher/refresh.sh --area frontend/components
```

### "No commits found"

If analysis shows 0 commits:
- Check the area path is correct
- Try a longer timeframe (`--depth deep`)
- Verify commits exist in that area: `git log -- frontend/components`

### Low Quality Guidelines

If generated guidelines are too generic:
- Increase analysis depth: `--depth deep`
- Ensure PR reviews exist and are being analyzed
- Add area-specific config (`.claude/area-configs/`)
- Enhance generated guidelines with code examples

## Development

### Running Tests

```bash
# Test on a small area
python3 skills/guideline-refresher/refresh_guidelines.py \
  --area . \
  --depth quick

# Verify output
cat .claude/guidelines/*.md
cat .claude/reports/*.md
```

### Extending the Skill

Add custom analyzers in `refresh_guidelines.py`:

```python
def analyze_security_patterns(self):
    """Custom analyzer for security patterns"""
    # Search for security-related patterns
    security_commits = self.search_commits(['security', 'auth', 'sanitize'])
    self.findings['security_patterns'] = security_commits
```

Add custom review themes in `config.json`:

```json
{
  "review_themes": {
    "custom_theme": ["keyword1", "keyword2", "keyword3"]
  }
}
```

## FAQ

**Q: Will this overwrite my carefully crafted guidelines?**
A: No. Previous guidelines are automatically backed up. Plus, generated guidelines are meant to be enhanced with code examples and context.

**Q: Can I use this without GitHub?**
A: Yes. Without `gh` CLI, it analyzes git history and file patterns. You'll miss PR review insights, but it still works.

**Q: How often should I refresh guidelines?**
A: Depends on how fast your codebase evolves. After migrations: immediately. Active areas: weekly/monthly. Stable areas: quarterly.

**Q: Can I customize what gets analyzed?**
A: Yes. Edit `config.json` or create area-specific configs in `.claude/area-configs/`.

**Q: Why are my guidelines empty or generic?**
A: Increase `--depth` or check that:
- The area path is correct
- Commits exist in that area
- PR reviews exist (if using gh CLI)

**Q: Can I run this on multiple areas at once?**
A: Yes, script it:
```bash
for area in frontend/components backend/api utils; do
  ./skills/guideline-refresher/refresh.sh --area "$area"
done
```

## Contributing

Improvements welcome! Areas for enhancement:

- Additional analyzers (test coverage, bundle size, etc.)
- More sophisticated pattern detection
- Integration with other tools (Jira, Linear, etc.)
- Support for other VCS besides git
- Machine learning for pattern recognition

## License

Same license as the parent repository.

## Credits

Created as a Claude Code skill to solve the problem of stale coding guidelines. Inspired by the reality that what teams actually do often differs from what's documented.

---

**Pro Tip:** After a major migration or refactoring, run a deep analysis on affected areas. The skill will extract patterns from the evolution and generate guidelines that reflect your new reality, not your old documentation.
