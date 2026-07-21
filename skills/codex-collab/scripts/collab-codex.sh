#!/usr/bin/env bash
set -uo pipefail

usage() {
  echo "usage: collab-codex.sh ask <workdir> <effort> <prompt-file>" >&2
  echo "       collab-codex.sh resume <workdir> <thread-id> <effort> <prompt-file>" >&2
  echo "       collab-codex.sh review <workdir> [codex-review-args...]" >&2
  exit 2
}

thread_id_from() {
  grep -m1 '"type":"thread.started"' "$1" | sed -E 's/.*"thread_id":"([^"]+)".*/\1/'
}

logdir_for() {
  local dir=${CODEX_COLLAB_DIR:-}
  if [[ -z "$dir" ]]; then
    mktemp -d "${TMPDIR:-/tmp}/codex-collab-XXXXXX"
    return
  fi
  mkdir -p "$dir"
  printf '%s\n' "$dir"
}

new_log() {
  local log
  log=$(mktemp "$1/codex-XXXXXX")
  mv "$log" "$log.jsonl"
  printf '%s\n' "$log.jsonl"
}

emit() {
  printf 'thread_id: %s\n---\n' "$1"
  cat "$2"
}

cmd=${1:-}; [[ -n "$cmd" ]] || usage; shift

case "$cmd" in
  ask)
    [[ $# -eq 3 ]] || usage
    workdir=$1 effort=$2 prompt=$3
    dir=$(logdir_for "$workdir")
    log=$(new_log "$dir")
    msg="$dir/last-message.txt"
    : > "$msg"
    codex exec --sandbox read-only -c approval_policy=never --json -C "$workdir" \
      -c model_reasoning_effort="$effort" \
      -o "$msg" \
      - < "$prompt" > "$log"
    rc=$?
    tid=$(thread_id_from "$log")
    if [[ $rc -ne 0 || ! -s "$msg" ]]; then
      echo "collab-codex: ask failed (rc=$rc, log=$log)" >&2
      exit "${rc/#0/1}"
    fi
    if [[ -z "$tid" ]]; then
      echo "collab-codex: no thread id found — resume disabled for this ask (log=$log)" >&2
      tid=unknown
    fi
    emit "$tid" "$msg"
    ;;
  resume)
    [[ $# -eq 4 ]] || usage
    workdir=$1 session=$2 effort=$3 prompt=$4
    dir=$(logdir_for "$workdir")
    log=$(new_log "$dir")
    msg="$dir/last-message.txt"
    : > "$msg"
    (cd "$workdir" && codex exec resume "$session" -c sandbox_mode="read-only" -c approval_policy=never --json \
      -c model_reasoning_effort="$effort" \
      -o "$msg" \
      - < "$prompt" > "$log")
    rc=$?
    if [[ $rc -ne 0 || ! -s "$msg" ]]; then
      echo "collab-codex: resume failed (rc=$rc, log=$log)" >&2
      exit "${rc/#0/1}"
    fi
    emit "$session" "$msg"
    ;;
  review)
    [[ $# -ge 1 ]] || usage
    workdir=$1; shift
    (cd "$workdir" && codex exec review -c sandbox_mode="read-only" -c approval_policy=never "$@")
    ;;
  *) usage ;;
esac
