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

mkdir -p "$TMP/bin" "$TMP/work"
cat > "$TMP/bin/codex" <<'SHIM'
#!/usr/bin/env bash
echo "$@" >> "${CODEX_SHIM_ARGS}"
if [[ "${CODEX_SHIM_EXIT:-0}" != "0" ]]; then exit "${CODEX_SHIM_EXIT}"; fi
if [[ "$1" == "exec" && "$2" != "review" ]]; then
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

SUT="$HERE/e2e-codex.sh"
PROMPT="$TMP/prompt.txt"; echo "do the thing" > "$PROMPT"

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" run "$TMP/work" high "$PROMPT")
assert "run prints thread id" "aaaa-1111-bbbb-2222" "$out"
args=$(cat "$CODEX_SHIM_ARGS")
case "$args" in *"--sandbox workspace-write"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: run passes --sandbox workspace-write";; esac
case "$args" in *"approval_policy=never"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: run passes approval_policy=never";; esac
case "$args" in *"sandbox_workspace_write.network_access=true"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: run passes network_access=true";; esac
case "$args" in *"model_reasoning_effort=high"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: run passes effort";; esac
case "$args" in *"-C $TMP/work"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: run passes -C workdir";; esac

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" resume "$TMP/work" aaaa-1111-bbbb-2222 low "$PROMPT")
assert "resume prints thread id" "aaaa-1111-bbbb-2222" "$out"
args=$(cat "$CODEX_SHIM_ARGS")
case "$args" in *"resume aaaa-1111-bbbb-2222"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: resume passes session id";; esac

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" review "$TMP/work" --commit deadbeef)
case "$out" in *"REVIEW: 1 finding"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: review passes output through";; esac
args=$(cat "$CODEX_SHIM_ARGS")
case "$args" in *"--commit deadbeef"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: review forwards scope args";; esac

: > "$CODEX_SHIM_ARGS"
out=$("$SUT" audit "$TMP/work" "$PROMPT")
args=$(cat "$CODEX_SHIM_ARGS")
case "$args" in *"--sandbox read-only"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: audit passes --sandbox read-only";; esac
case "$args" in *"-C $TMP/work"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: audit passes -C workdir";; esac
case "$args" in *"model_reasoning_effort=high"*) PASS=$((PASS+1));; *) FAIL=$((FAIL+1)); echo "FAIL: audit pins high effort";; esac

CODEX_SHIM_EXIT=3 "$SUT" run "$TMP/work" low "$PROMPT" >/dev/null 2>&1
assert "run propagates codex exit code" "3" "$?"

nothread_out=$(CODEX_SHIM_NO_THREAD=1 "$SUT" run "$TMP/work" low "$PROMPT" 2>/dev/null)
nothread_rc=$?
assert "run exits 1 when no thread.started" "1" "$nothread_rc"
assert "run prints nothing when no thread.started" "" "$nothread_out"

echo "---"
echo "pass=$PASS fail=$FAIL"
[[ "$FAIL" == "0" ]]
