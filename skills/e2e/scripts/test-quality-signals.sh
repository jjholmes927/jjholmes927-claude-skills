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
  if [[ "$haystack" == *"$needle"* ]]; then PASS=$((PASS+1)); else
    FAIL=$((FAIL+1)); echo "FAIL: $desc"; echo "  missing: $needle"
  fi
}

SUT="$HERE/quality-signals.sh"
REPO="$TMP/repo"
mkdir -p "$TMP/bin" "$TMP/all-tools" "$REPO"
export XDG_STATE_HOME="$TMP/state"
export QUALITY_COVERAGE_CMD="true"
export TOOL_LOG="$TMP/tools.log"
LEDGER="$XDG_STATE_HOME/e2e/quality-signals.tsv"

cat > "$TMP/all-tools/crapper" <<'SHIM'
#!/usr/bin/env bash
echo "crapper $*" >> "$TOOL_LOG"
mkdir -p .metrics
echo "Function    Namespace          CC    Cov%     CRAP"
echo "------------------------------------------------"
echo "useThing    app.hooks.thing    29    0.0%    870.0"
echo "helper      app.hooks.thing     4   50.0%     15.0"
echo "tidy        app.hooks.thing     1  100.0%      1.0"
SHIM
cat > "$TMP/all-tools/dryer" <<'SHIM'
#!/usr/bin/env bash
echo "dryer $*" >> "$TOOL_LOG"
echo "DUPLICATE score=1.00"
echo "  app/hooks/thing.ts:3-9"
echo "  app/other/copy.ts:10-16"
echo "DUPLICATE score=1.00"
echo "  app/api/gen-api.ts:1-8"
echo "  app/hooks/thing.ts:3-9"
echo "DUPLICATE score=0.90"
echo "  app/other/copy.ts:1-5"
echo "  app/other/more.ts:1-5"
SHIM
cat > "$TMP/all-tools/rubycritic" <<'SHIM'
#!/usr/bin/env bash
echo "rubycritic $*" >> "$TOOL_LOG"
[[ -f .reek.yml ]] && echo "reek config present" >> "$TOOL_LOG"
echo "Thing:"
echo "  Rating:       F"
echo "  Smells:"
echo "    * (HighComplexity) Thing#call has a flog score of 47"
echo "      - app/models/thing.rb:3"
echo "Fine:"
echo "  Rating:       A"
SHIM
printf '#!/bin/sh\nexit 1\n' > "$TMP/bin/security"
printf '#!/bin/sh\necho "pnpm $*" >> "$TOOL_LOG"\n' > "$TMP/all-tools/pnpm"
chmod +x "$TMP/all-tools/"* "$TMP/bin/security"
for tool in git python3 awk sed grep sort cut head tail wc tr paste xargs date mktemp dirname basename cat cp rm mkdir touch hostname bash env; do
  ln -s "$(command -v "$tool")" "$TMP/bin/$tool"
done

cd "$REPO" || exit 1
git init -q -b main
mkdir -p app/hooks app/other app/api app/models app/__tests__
echo "export const copy = 1" > app/other/copy.ts
git add . && git -c user.name=t -c user.email=t@t commit -qm base
git switch -q -c feature
echo "export function useThing() {}" > app/hooks/thing.ts
printf '// DO NOT MODIFY: generated\nexport const api = 1\n' > app/api/gen-api.ts
echo "test('x', () => {})" > app/__tests__/thing.test.ts
echo "class Thing; end" > app/models/thing.rb
git add . && git -c user.name=t -c user.email=t@t commit -qm feature

: > "$TOOL_LOG"
out=$(PATH="$TMP/all-tools:$TMP/bin" "$SUT" main)
rc=$?
report=$(cat .e2e/quality-signals.md)
assert "run exits 0" "0" "$rc"
assert "run prints the report path" ".e2e/quality-signals.md" "$out"
contains "report lists the risky function" '`useThing` in `app.hooks.thing`: CRAP 870.0, complexity 29, coverage 0.0%' "$report"
contains "report counts the 10 to 30 band" "1 more between 10 and 30." "$report"
contains "report keeps the duplicate touching a changed file" '`app/hooks/thing.ts:3-9` and `app/other/copy.ts:10-16`' "$report"
assert "report drops duplicates with generated code" "" "$(grep gen-api <<< "$report")"
assert "report drops duplicates not touching changed files" "" "$(grep more.ts <<< "$report")"
contains "report lists the F class" '- F: `Thing`' "$report"
contains "report lists the complex method" '- Thing#call has a flog score of 47 (`app/models/thing.rb:3`)' "$report"
assert "crapper scores only changed source" "crapper --use-existing-coverage app/hooks/thing.ts" "$(grep '^crapper' "$TOOL_LOG")"
assert "dryer scans the changed file's top-level folder" "dryer app" "$(grep '^dryer' "$TOOL_LOG")"
assert "rubycritic gets only changed Ruby" "app/models/thing.rb" "$(grep '^rubycritic' "$TOOL_LOG" | awk '{print $NF}')"
contains "rubycritic sees the noise config" "reek config present" "$(cat "$TOOL_LOG")"
assert "temporary reek config is removed" "no" "$([[ -e .reek.yml ]] && echo yes || echo no)"
assert "tool output folders are removed" "no" "$([[ -e .metrics ]] && echo yes || echo no)"
assert "working tree stays clean" "" "$(git status --porcelain)"
contains "run is recorded" '"event": "quality_signals_run"' "$(cat "$LEDGER")"
contains "run records the counts" '"crap_30_plus": 1, "crap_10_30": 1, "duplicates": 1, "ruby_flagged": 2' "$(cat "$LEDGER")"

printf '{"scripts": {"test": "vitest --project=unit --run"}}\n' > package.json
touch pnpm-lock.yaml
: > "$TOOL_LOG"
QUALITY_COVERAGE_CMD="" PATH="$TMP/all-tools:$TMP/bin" "$SUT" main > /dev/null
assert "a Vitest project gets coverage for the changed tests only" \
  "pnpm run test --changed main --coverage.include=app/hooks/thing.ts --coverage.enabled --coverage.provider=v8 --coverage.reporter=lcovonly --coverage.reportsDirectory=coverage --coverage.reportOnFailure" \
  "$(grep '^pnpm' "$TOOL_LOG")"
rm package.json pnpm-lock.yaml

out=$(PATH="$TMP/bin" "$SUT" main)
report=$(cat .e2e/quality-signals.md)
contains "missing crapper is reported" "crapper: not run (not installed)" "$report"
contains "missing rubycritic is reported" "rubycritic: not run (not installed)" "$report"
contains "missing tools are recorded" '"not_run": "crapper,dryer,rubycritic"' "$(tail -n 1 "$LEDGER")"

out=$(PATH="$TMP/all-tools:$TMP/bin" "$SUT" no-such-ref)
assert "a bad base still exits 0" "0" "$?"
contains "a bad base is reported" "Not run: could not diff against \`no-such-ref\`" "$(cat .e2e/quality-signals.md)"

PATH="$TMP/bin" "$SUT" record 2 1
contains "outcome is recorded" '"event": "quality_signals_outcome"' "$(tail -n 1 "$LEDGER")"
contains "outcome records the counts" '"accepted": 2, "dismissed": 1' "$(tail -n 1 "$LEDGER")"
PATH="$TMP/bin" "$SUT" record two 1 2>/dev/null
assert "record rejects a non-number" "2" "$?"
PATH="$TMP/bin" "$SUT" 2>/dev/null
assert "no arguments is a usage error" "2" "$?"

echo "PASS=$PASS FAIL=$FAIL"
[[ $FAIL -eq 0 ]]
