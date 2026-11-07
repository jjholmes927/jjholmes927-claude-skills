STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/e2e"

emit() {
  local event=$1; shift
  local repo head payload key
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  head=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  payload=$(python3 - "$event" "$repo" "$head" "$(agent-host-name 2>/dev/null || hostname -s)" "$@" <<'PY'
import json, sys
event, repo, head, host, *pairs = sys.argv[1:]
fields = {"event": event, "repo": repo, "head": head, "host.name": host}
for pair in pairs:
    name, _, value = pair.partition("=")
    fields[name] = int(value) if value.isdigit() else value
print(json.dumps(fields))
PY
)
  mkdir -p "$STATE_DIR"
  printf '%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$payload" >> "$STATE_DIR/ledger.tsv"
  [[ ${E2E_LEDGER:-on} == off ]] && return 0
  key=$(security find-generic-password -s honeycomb-agent-traces -w 2>/dev/null) || return 0
  [[ -n "$key" ]] || return 0
  curl -s -m 5 -X POST "https://api.eu1.honeycomb.io/1/events/workflow-ledger" \
    -H "X-Honeycomb-Team: $key" -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1 || true
}
