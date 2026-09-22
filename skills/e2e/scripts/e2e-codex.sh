#!/usr/bin/env bash
set -uo pipefail

usage() {
  echo "usage: e2e-codex.sh run <workdir> <effort> <prompt-file>" >&2
  echo "       e2e-codex.sh resume <workdir> <session-id> <effort> <prompt-file>" >&2
  echo "       e2e-codex.sh review <workdir> [codex-review-args...]" >&2
  echo "       e2e-codex.sh audit <workdir> <prompt-file>" >&2
  exit 2
}

thread_id_from() {
  grep -m1 '"type":"thread.started"' "$1" | sed -E 's/.*"thread_id":"([^"]+)".*/\1/'
}

cmd=${1:-}; [[ -n "$cmd" ]] || usage; shift

[[ ${E2E_CHILD:-0} != 1 ]] || { echo "e2e-codex: children cannot launch another E2E route" >&2; exit 2; }
case "$cmd" in
  run|resume) model=${E2E_IMPLEMENTER_MODEL:-} ;;
  review|audit) model=${E2E_REVIEWER_MODEL:-} ;;
  *) usage ;;
esac
[[ -n "$model" ]] || { echo "e2e-codex: select E2E_IMPLEMENTER_MODEL or E2E_REVIEWER_MODEL for this route" >&2; exit 2; }

case "$cmd" in
  run)
    [[ $# -eq 3 ]] || usage
    workdir=$1 effort=$2 prompt=$3
    mkdir -p "$workdir/.e2e"
    log=$(mktemp "$workdir/.e2e/codex-XXXXXX"); mv "$log" "$log.jsonl"; log="$log.jsonl"
    E2E_CHILD=1 codex exec --model "$model" --sandbox workspace-write -c approval_policy=never --json -C "$workdir" \
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
    (cd "$workdir" && E2E_CHILD=1 codex exec resume "$session" --model "$model" -c sandbox_mode="workspace-write" -c approval_policy=never --json \
      -c sandbox_workspace_write.network_access=true \
      -c model_reasoning_effort="$effort" \
      -o "$workdir/.e2e/last-message.txt" \
      - < "$prompt" > "$log")
    rc=$?
    [[ -s "$log" ]] || rc=1
    printf '%s\n' "$session"
    exit "$rc"
    ;;
  review)
    [[ $# -ge 1 ]] || usage
    workdir=$1; shift
    case "${1:-}" in
      --commit|--base) [[ $# -eq 2 && -n "$2" ]] || usage ;;
      --uncommitted) [[ $# -eq 1 ]] || usage ;;
      *) usage ;;
    esac
    (cd "$workdir" && E2E_CHILD=1 codex exec review --model "$model" --ignore-user-config --ignore-rules --ephemeral -c sandbox_mode="read-only" -c approval_policy=never "$@")
    ;;
  audit)
    [[ $# -eq 2 ]] || usage
    workdir=$1 prompt=$2
    E2E_CHILD=1 codex exec --model "$model" --ignore-user-config --ignore-rules --ephemeral --sandbox read-only -c approval_policy=never -C "$workdir" \
      -c model_reasoning_effort=high \
      - < "$prompt"
    ;;
  *) usage ;;
esac
