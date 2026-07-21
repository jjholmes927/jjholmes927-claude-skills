# Claude Skills

A collection of Claude Code commands and skills to enhance your development workflow, packaged as the `joel-workflow` plugin.

## Marketplace Overview

This repository is a Claude Code plugin marketplace containing one plugin, `joel-workflow`: workflow slash commands plus skills that automate common development tasks.

## Available Commands

| Command | Description |
|---------|-------------|
| `/ship` | End-to-end ship workflow: format, commit, push, PR, CI watch, review consolidation |
| `/review-pr` | Structured multi-pass pull request review |
| `/verify-ui` | Verify a UI flow in a real browser via agent-browser (localhost or staging) |
| `/pick-up-linear-ticket` | Claim a Linear ticket and set up a branch to start implementation |
| `/brag-doc` | Generate weekly brag doc entries from GitHub activity |
| `/skill-reviewer` | Review a Claude Code skill for structural and domain quality |

## Available Skills

### 📋 [Guideline Refresher](skills/guideline-refresher/)

Auto-refresh coding guidelines based on codebase patterns, PR reviews, and approved code.

**What it does:** Analyzes your git history, merged PRs, and review comments to generate evidence-based coding guidelines that reflect your actual practices—not outdated documentation.

**Perfect for:**
- Keeping guidelines current after migrations or refactorings
- Documenting actual team patterns from approved code
- Generating area-specific rules (frontend, backend, utils, etc.)

**Links:**
- 📖 [Full Documentation](skills/guideline-refresher/README.md)
- 🚀 [Usage Examples](EXAMPLES.md)

### 🚢 [E2E](skills/e2e/)

Full delivery pipeline: Claude/Fable plans with one approval gate, codex/Sol implements each task headlessly with graded reasoning effort, dual review with fix loops, then ship to PR with CI watch.

### 👀 [Codex Collab](skills/codex-collab/)

Pulls codex/Sol in as a read-only second pair of eyes on whatever workflow is running: cross-model review, corroboration of a conclusion, or a blind second opinion on a design — with graded reasoning effort and honest disagreement reporting.

## Installation

### From Marketplace (Recommended)

```bash
# Add marketplace
/plugin marketplace add jjholmes927/jjholmes927-claude-skills

# Install plugin
/plugin install joel-workflow@jjholmes927-claude-skills
```

### Manual Installation

```bash
# Clone and install all skills
git clone https://github.com/jjholmes927/jjholmes927-claude-skills.git
cd jjholmes927-claude-skills
./install.sh
```

## Quick Start

Once installed, skills work automatically:

```
You: "Refresh guidelines for frontend/components"
Claude: [Uses guideline-refresher skill automatically]
```

Or run directly from command line:
```bash
~/.claude/skills/guideline-refresher/refresh.sh --area frontend/components
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
