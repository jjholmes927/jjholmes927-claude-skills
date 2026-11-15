#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
current=$(git config --get core.hooksPath || true)
default_hook=$(git rev-parse --git-path hooks/pre-push)
if [[ -n "$current" && "$current" != .githooks ]] || [[ -z "$current" && -e "$default_hook" ]]; then
  echo "Existing Git hooks preserved. Compose the version check into your hook setup before enabling .githooks." >&2
  exit 1
fi
git config --local core.hooksPath .githooks
echo "Version pre-push hook enabled for this checkout."
