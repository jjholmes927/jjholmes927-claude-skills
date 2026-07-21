#!/usr/bin/env bash
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

assert() {
  local desc=$1 expected=$2 actual=$3
  if [[ "$expected" == "$actual" ]]; then PASS=$((PASS+1)); else
    FAIL=$((FAIL+1)); echo "FAIL: $desc"; echo "  expected: $expected"; echo "  actual:   $actual"
  fi
}

contains() {
  local desc=$1 needle=$2 haystack=$3
  case "$haystack" in *"$needle"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: $desc";; esac
}

mkdir -p "$TMP/bin" "$TMP/work"
cat > "$TMP/bin/codex" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "${CODEX_SHIM_ARGS}"
if [[ "${CODEX_SHIM_EXIT:-0}" != "0" ]]; then exit "${CODEX_SHIM_EXIT}"; fi
if [[ "$1" == "exec" && "$2" != "review" ]]; then
  out=""
  prev=""
  for a in "$@"; do
    [[ "$prev" == "-o" ]] && out="$a"
    prev="$a"
  done
  if [[ -n "$out" && -z "${CODEX_SHIM_NO_MSG:-}" ]]; then echo "SOL SAYS: verdict" > "$out"; fi
  if [[ -z "${CODEX_SHIM_NO_THREAD:-}" ]]; then
    echo '{"type":"thread.started","thread_id":"aaaa-1111-bbbb-2222"}'
    echo '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}'
  fi
elif [[ "$2" == "review" ]]; then
  echo "REVIEW: 1 finding — example"
fi
SHIM
chmod +x "$TMP/bin/codex"
export PATH="$TMP/bin:$PATH"
export CODEX_SHIM_ARGS="$TMP/args.log"

SUT="$HERE/collab-codex.sh"
PROMPT="$TMP/prompt.txt"; echo "poke holes in this" > "$PROMPT"

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" ask "$TMP/work" high "$PROMPT")
contains "ask prints thread id" "thread_id: aaaa-1111-bbbb-2222" "$out"
contains "ask prints Sol's reply" "SOL SAYS: verdict" "$out"
args=$(cat "$CODEX_SHIM_ARGS")
contains "ask passes --sandbox read-only" "--sandbox read-only" "$args"
contains "ask passes approval_policy=never" "approval_policy=never" "$args"
contains "ask passes effort" "model_reasoning_effort=high" "$args"
contains "ask passes -C workdir" "-C $TMP/work" "$args"
[[ ! -d "$TMP/work/.codex-collab" ]] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "FAIL: ask never writes logs into the workdir"; }

: > "$CODEX_SHIM_ARGS"
out=$(CODEX_COLLAB_DIR="$TMP/scratch" "$SUT" ask "$TMP/work" low "$PROMPT")
[[ -d "$TMP/scratch" && ! -d "$TMP/work/.codex-collab" ]] && PASS=$((PASS+1)) || { FAIL=$((FAIL+1)); echo "FAIL: CODEX_COLLAB_DIR keeps logs out of workdir"; }

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" resume "$TMP/work" aaaa-1111-bbbb-2222 low "$PROMPT")
contains "resume prints thread id" "thread_id: aaaa-1111-bbbb-2222" "$out"
contains "resume prints Sol's reply" "SOL SAYS: verdict" "$out"
args=$(cat "$CODEX_SHIM_ARGS")
contains "resume passes session id" "resume aaaa-1111-bbbb-2222" "$args"
contains "resume forces read-only sandbox" "sandbox_mode=read-only" "$args"

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" review "$TMP/work" --base main)
contains "review passes output through" "REVIEW: 1 finding" "$out"
args=$(cat "$CODEX_SHIM_ARGS")
contains "review forwards scope args" "--base main" "$args"
contains "review forces read-only sandbox" "sandbox_mode=read-only" "$args"
contains "review forces approval_policy=never" "approval_policy=never" "$args"

CODEX_SHIM_EXIT=3 "$SUT" ask "$TMP/work" low "$PROMPT" >/dev/null 2>&1
assert "ask propagates codex exit code" "3" "$?"

nothread_out=$(CODEX_SHIM_NO_THREAD=1 "$SUT" ask "$TMP/work" low "$PROMPT" 2>/dev/null)
nothread_rc=$?
assert "ask still succeeds when no thread.started" "0" "$nothread_rc"
contains "ask degrades to thread_id unknown" "thread_id: unknown" "$nothread_out"
contains "ask still prints the reply without a thread id" "SOL SAYS: verdict" "$nothread_out"

nomsg_out=$(CODEX_SHIM_NO_MSG=1 "$SUT" ask "$TMP/work" low "$PROMPT" 2>/dev/null)
assert "ask exits 1 when reply is empty" "1" "$?"

echo "---"
echo "pass=$PASS fail=$FAIL"
[[ "$FAIL" == "0" ]]
