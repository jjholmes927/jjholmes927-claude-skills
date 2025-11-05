# Usage Guide

Quick reference for using the Claude Skills in this repository.

## Installation

### Quick Install (All Skills)

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-skills.git
cd claude-skills

# Install all skills
./install.sh
```

### Install Specific Skills

```bash
# Install only guideline-refresher
./install.sh guideline-refresher
```

### Manual Installation

```bash
# Copy skill to Claude skills directory
cp -r skills/guideline-refresher ~/.claude/skills/

# Or create symlink for development
ln -s "$(pwd)/skills/guideline-refresher" ~/.claude/skills/guideline-refresher
```

## Guideline Refresher

### From Claude Code

Simply tell Claude what you need:

```
"Refresh guidelines for frontend/components"
"Update coding guidelines for backend/api based on recent changes"
"Analyze code patterns in utils and create guidelines"
```

Claude will automatically use the guideline-refresher skill.

### Command Line

```bash
# Using the helper script
./skills/guideline-refresher/refresh.sh --area frontend/components --depth standard

# Or directly with Python
python3 skills/guideline-refresher/refresh_guidelines.py \
  --area frontend/components \
  --depth standard
```

### After Installation

```bash
# If installed to ~/.claude/skills
~/.claude/skills/guideline-refresher/refresh.sh --area frontend/components
```

## Analysis Depths

| Depth | When to Use | Timeframe | PRs |
|-------|-------------|-----------|-----|
| **quick** | After sprints, quick checks | 30 days | 20 |
| **standard** | Regular updates | 90 days | 50 |
| **deep** | After migrations, comprehensive analysis | 180 days | 100 |

## Examples

### Example 1: After Frontend Migration

```bash
# You migrated from Vue to React
./skills/guideline-refresher/refresh.sh \
  --area frontend/components \
  --depth deep

# Result: Guidelines reflecting React patterns, hooks usage, TypeScript adoption
```

### Example 2: Standardizing API Patterns

```bash
# Document actual API patterns
./skills/guideline-refresher/refresh.sh \
  --area backend/api \
  --depth standard

# Result: Error handling patterns, validation, auth/authz guidelines
```

### Example 3: Quick Sprint Review

```bash
# Check if patterns changed during sprint
./skills/guideline-refresher/refresh.sh \
  --area utils \
  --depth quick

# Result: Fast scan of last 30 days
```

## Output Files

After running, check:

### Guidelines
```bash
cat .claude/guidelines/frontend_components.md
```

Evidence-based guidelines including:
- Technology focus
- File organization
- Naming conventions
- Code review themes
- Recent evolution
- Specific recommendations

### Report
```bash
cat .claude/reports/guideline-refresh-20250105_143022.md
```

Detailed analysis with:
- Complete metrics
- Key findings
- Sample review feedback
- Next steps

## Tips

### 1. Be Specific with Areas

✅ **Good:**
```bash
--area frontend/components
--area backend/api/services
--area utils/helpers
```

❌ **Too Broad:**
```bash
--area frontend        # Too general
--area src            # Entire codebase
```

### 2. Add Code Examples

Generated guidelines are evidence-based but need examples:

```markdown
## Component Structure

**Pattern:** Functional components with hooks

### Example
\`\`\`typescript
interface UserCardProps {
  user: User;
  onEdit: (user: User) => void;
}

export function UserCard({ user, onEdit }: UserCardProps) {
  // Implementation
}
\`\`\`
```

### 3. Review Before Committing

Always review generated guidelines:
- Do metrics make sense?
- Are recommendations aligned with project values?
- Need more code examples?

### 4. Schedule Regular Updates

```bash
# Weekly for active areas
0 0 * * 1 ~/scripts/refresh-frontend.sh

# Monthly for stable areas
0 0 1 * * ~/scripts/refresh-backend.sh
```

## Troubleshooting

### gh CLI not found

PR analysis requires GitHub CLI:

```bash
# Install
brew install gh

# Authenticate
gh auth login
```

### No commits found

Try:
- Verify area path: `ls -la frontend/components`
- Use longer timeframe: `--depth deep`
- Check git history: `git log -- frontend/components`

### Guidelines too generic

- Increase depth: `--depth deep`
- Ensure PR reviews exist
- Add area-specific config
- Enhance with code examples

## Advanced Usage

### Custom Configuration

Create `.claude/area-configs/frontend-components.json`:

```json
{
  "patterns_to_track": [
    "component composition",
    "state management"
  ],
  "required_sections": [
    "Component Structure",
    "Testing Requirements"
  ]
}
```

### Batch Processing

```bash
# Refresh multiple areas
for area in frontend/components backend/api utils; do
  ./skills/guideline-refresher/refresh.sh --area "$area"
done
```

### CI/CD Integration

See `skills/guideline-refresher/README.md` for GitHub Actions example.

## Getting Help

### Check Documentation
```bash
# Skill README
cat skills/guideline-refresher/README.md

# Command help
python3 skills/guideline-refresher/refresh_guidelines.py --help
```

### Verify Installation
```bash
ls -la ~/.claude/skills/guideline-refresher/
```

### Test Run
```bash
# Test on small area
./skills/guideline-refresher/refresh.sh --area . --depth quick
```

## Next Steps

1. **Install the skills:** Run `./install.sh`
2. **Test on a small area:** `refresh.sh --area utils --depth quick`
3. **Review output:** Check `.claude/guidelines/` and `.claude/reports/`
4. **Enhance guidelines:** Add code examples and context
5. **Commit:** Version control your guidelines
6. **Schedule updates:** Set up regular refreshes

## Contributing

To add new skills:

1. Create `skills/{skill-name}/`
2. Add `SKILL.md` (skill definition)
3. Add implementation files
4. Add `README.md`
5. Update main README
6. Update `plugin.json`

See existing skills for examples.
