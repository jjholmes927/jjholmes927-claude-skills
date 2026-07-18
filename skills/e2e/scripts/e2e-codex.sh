#!/usr/bin/env bash
set -uo pipefail

usage() {
  echo "usage: e2e-codex.sh run <workdir> <effort> <prompt-file>" >&2
  echo "       e2e-codex.sh resume <workdir> <session-id> <effort> <prompt-file>" >&2
  echo "       e2e-codex.sh review <workdir> [codex-review-args...]" >&2
  exit 2
}

thread_id_from() {
  grep -m1 '"type":"thread.started"' "$1" | sed -E 's/.*"thread_id":"([^"]+)".*/\1/'
}

cmd=${1:-}; [[ -n "$cmd" ]] || usage; shift

case "$cmd" in
  run)
    [[ $# -eq 3 ]] || usage
    workdir=$1 effort=$2 prompt=$3
    mkdir -p "$workdir/.e2e"
    log=$(mktemp "$workdir/.e2e/codex-XXXXXX"); mv "$log" "$log.jsonl"; log="$log.jsonl"
    codex exec --sandbox workspace-write -c approval_policy=never --json -C "$workdir" \
      -c sandbox_workspace_write.network_access=true \
      -c model_reasoning_effort="$effort" \
      -o "$workdir/.e2e/last-message.txt" \
      - < "$prompt" > "$log"
    rc=$?
    tid=$(thread_id_from "$log")
    [[ -n "$tid" ]] && printf '%s\n' "$tid"
    [[ $rc -eq 0 && -n "$tid" ]] || exit "${rc/#0/1}"
    ;;
  resume)
    [[ $# -eq 4 ]] || usage
    workdir=$1 session=$2 effort=$3 prompt=$4
    mkdir -p "$workdir/.e2e"
    log=$(mktemp "$workdir/.e2e/codex-XXXXXX"); mv "$log" "$log.jsonl"; log="$log.jsonl"
    codex exec resume "$session" --sandbox workspace-write -c approval_policy=never --json -C "$workdir" \
      -c sandbox_workspace_write.network_access=true \
      -c model_reasoning_effort="$effort" \
      -o "$workdir/.e2e/last-message.txt" \
      - < "$prompt" > "$log"
    rc=$?
    printf '%s\n' "$session"
    exit "$rc"
    ;;
  review)
    [[ $# -ge 1 ]] || usage
    workdir=$1; shift
    (cd "$workdir" && codex exec review "$@")
    ;;
  *) usage ;;
esac
