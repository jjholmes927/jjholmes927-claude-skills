#!/bin/bash
# Installation script for Claude Skills

set -e

CLAUDE_SKILLS_DIR="${HOME}/.claude/skills"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Claude Skills Installer"
echo ""

# Check if Claude skills directory exists
if [ ! -d "$CLAUDE_SKILLS_DIR" ]; then
    echo "Creating Claude skills directory: $CLAUDE_SKILLS_DIR"
    mkdir -p "$CLAUDE_SKILLS_DIR"
fi

# Function to install a skill
install_skill() {
    local skill_name="$1"
    local source_dir="$SCRIPT_DIR/skills/$skill_name"
    local target_dir="$CLAUDE_SKILLS_DIR/$skill_name"

    if [ ! -d "$source_dir" ]; then
        echo "❌ Skill not found: $skill_name"
        return 1
    fi

    echo "📦 Installing $skill_name..."

    # Check if skill already exists
    if [ -d "$target_dir" ]; then
        read -p "   Skill already exists. Overwrite? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "   Skipped."
            return 0
        fi
        rm -rf "$target_dir"
    fi

    # Copy skill
    cp -r "$source_dir" "$target_dir"

    # Make scripts executable
    find "$target_dir" -name "*.sh" -exec chmod +x {} \;
    find "$target_dir" -name "*.py" -exec chmod +x {} \;

    echo "   ✓ Installed to $target_dir"
}

# Parse arguments
if [ $# -eq 0 ]; then
    # Install all skills
    echo "Installing all skills..."
    echo ""

    for skill_dir in "$SCRIPT_DIR/skills/"*; do
        if [ -d "$skill_dir" ]; then
            skill_name=$(basename "$skill_dir")
            install_skill "$skill_name"
        fi
    done
else
    # Install specific skills
    for skill_name in "$@"; do
        install_skill "$skill_name"
    done
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Installed skills are available in: $CLAUDE_SKILLS_DIR"
echo ""
echo "Usage:"
echo "  - In Claude Code, skills will be automatically detected"
echo "  - Or use directly: ~/.claude/skills/guideline-refresher/refresh.sh --area frontend/components"
echo ""
echo "To verify installation:"
echo "  ls -la $CLAUDE_SKILLS_DIR"
