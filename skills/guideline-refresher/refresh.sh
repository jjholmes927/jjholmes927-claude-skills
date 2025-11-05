#!/bin/bash
# Integration script for Guideline Refresher skill
# Makes it easy to run the guideline refresh from command line

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AREA=""
DEPTH="standard"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --area)
            AREA="$2"
            shift 2
            ;;
        --depth)
            DEPTH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 --area <area> [--depth <quick|standard|deep>]"
            echo ""
            echo "Examples:"
            echo "  $0 --area frontend/components"
            echo "  $0 --area backend/api --depth deep"
            echo "  $0 --area utils/helpers --depth quick"
            echo ""
            echo "Options:"
            echo "  --area     Area of codebase to analyze (required)"
            echo "  --depth    Analysis depth: quick, standard, or deep (default: standard)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate area argument
if [ -z "$AREA" ]; then
    echo "Error: --area is required"
    echo "Usage: $0 --area <area> [--depth <quick|standard|deep>]"
    echo "Use --help for more information"
    exit 1
fi

# Validate depth argument
if [[ ! "$DEPTH" =~ ^(quick|standard|deep)$ ]]; then
    echo "Error: Invalid depth '$DEPTH'. Must be: quick, standard, or deep"
    exit 1
fi

# Run the Python script
echo "🔄 Refreshing guidelines for: $AREA"
echo ""

python3 "$SCRIPT_DIR/refresh_guidelines.py" --area "$AREA" --depth "$DEPTH"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Success! Next steps:"
    echo "   1. Review generated guidelines in .claude/guidelines/"
    echo "   2. Check analysis report in .claude/reports/"
    echo "   3. Add code examples to make guidelines more concrete"
    echo "   4. Commit changes when ready"
else
    echo ""
    echo "❌ Guideline refresh failed with exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi
