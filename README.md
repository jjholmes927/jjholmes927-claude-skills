# Claude Skills

A collection of Claude Code skills to enhance your development workflow.

## Skills

### Guideline Refresher

Automatically analyzes your codebase evolution and refreshes coding guidelines based on actual patterns, PR reviews, and approved code.

**Problem it solves:** Coding guidelines get stale after migrations and refactorings. This skill extracts truth from your codebase instead of relying on outdated documentation.

**Key features:**
- Analyzes git commit history for technology adoption and patterns
- Mines PR review comments to identify recurring feedback themes
- Examines file organization and naming conventions
- Generates evidence-based guidelines with specific recommendations
- Tracks changes from previous guidelines with automatic backups

**Quick start:**
```bash
# Analyze and refresh guidelines for a specific area
./skills/guideline-refresher/refresh.sh --area frontend/components --depth standard

# Or use directly with Python
python3 skills/guideline-refresher/refresh_guidelines.py --area backend/api --depth deep
```

**Documentation:** See [skills/guideline-refresher/README.md](skills/guideline-refresher/README.md)

## Installation

### As a Claude Code Plugin

```bash
# Clone this repository
git clone https://github.com/yourusername/claude-skills.git

# Copy skills to Claude skills directory
cp -r claude-skills/skills/* ~/.claude/skills/

# Or symlink for easier development
ln -s "$(pwd)/claude-skills/skills/guideline-refresher" ~/.claude/skills/guideline-refresher
```

### Individual Skills

Each skill can be copied independently to `~/.claude/skills/`:

```bash
cp -r skills/guideline-refresher ~/.claude/skills/
```

## Requirements

- **Python 3.7+** (for most skills)
- **git** (for guideline-refresher)
- **gh CLI** (optional, for PR analysis in guideline-refresher)

## Usage

Once installed, Claude Code will automatically detect and use these skills when appropriate. You can also invoke them explicitly:

**In Claude Code chat:**
> "Refresh guidelines for frontend/components"

**From command line:**
```bash
./skills/guideline-refresher/refresh.sh --area frontend/components
```

## Contributing

Contributions welcome! To add a new skill:

1. Create a directory under `skills/{skill-name}/`
2. Add `SKILL.md` with skill definition
3. Add implementation files (Python, shell scripts, etc.)
4. Add `README.md` with documentation
5. Update this README with the new skill
6. Update `plugin.json` with the skill metadata

## License

MIT - See LICENSE file for details
