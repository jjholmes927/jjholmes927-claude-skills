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
echo "DUPLICATE score=0.80"
echo "  app/hooks/thing.ts:8-10"
echo "  app/other/copy.ts:1-3"
SHIM
cat > "$TMP/all-tools/rubycritic" <<'SHIM'
#!/usr/bin/env bash
echo "rubycritic $*" >> "$TOOL_LOG"
[[ -f .reek.yml ]] && echo "reek config present" >> "$TOOL_LOG"
echo "Thing:"
echo "  Rating:       F"
echo "  Smells:"
echo "    * (HighComplexity) Thing#call has a flog score of 47"
echo "      - app/models/thing.rb:6"
echo "    * (VeryHighComplexity) Thing#old has a flog score of 61"
echo "      - app/models/thing.rb:2"
echo "    * (HighComplexity) Thing#last has a flog score of 30"
echo "      - app/models/thing.rb:10"
echo "Fine:"
echo "  Rating:       A"
SHIM
printf '#!/bin/sh\nexit 1\n' > "$TMP/bin/security"
printf '#!/bin/sh\necho "pnpm $*" >> "$TOOL_LOG"\n' > "$TMP/all-tools/pnpm"
printf '#!/bin/sh\necho test-host\n' > "$TMP/all-tools/agent-host-name"
chmod +x "$TMP/all-tools/"* "$TMP/bin/security"
for tool in git python3 awk sed grep sort cut head tail wc tr paste xargs date mktemp dirname basename cat cp rm mkdir touch hostname bash env; do
  ln -s "$(command -v "$tool")" "$TMP/bin/$tool"
done

cd "$REPO" || exit 1
git init -q -b main
mkdir -p app/hooks app/other app/api app/models app/__tests__ db
echo "export const copy = 1" > app/other/copy.ts
printf 'export function useThing() {\n  const a = 1\n  const b = 2\n  const c = 3\n  return a\n}\n\nexport function other() {\n  return 2\n}\n' > app/hooks/thing.ts
printf 'class Thing\n  def old\n    1\n  end\n\n  def call\n    2\n  end\n\n  def last\n    4\n  end\n\n  LIMIT = 1\nend\n' > app/models/thing.rb
git add . && git -c user.name=t -c user.email=t@t commit -qm base
git switch -q -c feature
sed -i.bak 's/return a/return b/' app/hooks/thing.ts && rm app/hooks/thing.ts.bak
sed -i.bak -e 's/^    2$/    3/' -e 's/LIMIT = 1/LIMIT = 2/' app/models/thing.rb && rm app/models/thing.rb.bak
printf '// DO NOT MODIFY: generated\nexport const api = 1\n' > app/api/gen-api.ts
echo "test('x', () => {})" > app/__tests__/thing.test.ts
printf '# This file is auto-generated from the current state of the database. Instead\n# of editing this file, please use the migrations feature of Active Record.\nActiveRecord::Schema[8.0].define(version: 1) do\nend\n' > db/schema.rb
git add . && git -c user.name=t -c user.email=t@t commit -qm feature

: > "$TOOL_LOG"
out=$(PATH="$TMP/all-tools:$TMP/bin" "$SUT" main)
rc=$?
report=$(cat .e2e/quality-signals.md)
assert "run exits 0" "0" "$rc"
assert "run prints the report path" ".e2e/quality-signals.md" "$out"
contains "report lists the risky function" '`useThing` in `app.hooks.thing`: CRAP 870.0, complexity 29, coverage 0.0%' "$report"
contains "report counts the 10 to 30 band" "1 more between 10 and 30." "$report"
contains "report marks the duplicate in changed lines" '`app/hooks/thing.ts:3-9` and `app/other/copy.ts:10-16` (changed by this branch)' "$report"
assert "report keeps an unmarked duplicate outside the changed lines" '- score 0.80: `app/hooks/thing.ts:8-10` and `app/other/copy.ts:1-3`' "$(grep 'score 0.80' <<< "$report")"
assert "report drops duplicates with generated code" "" "$(grep gen-api <<< "$report")"
assert "report drops duplicates not touching changed files" "" "$(grep more.ts <<< "$report")"
contains "report lists the F class" '- F: `Thing`' "$report"
contains "report marks the complex method the branch changed" '- Thing#call has a flog score of 47 (`app/models/thing.rb:6`) (changed by this branch)' "$report"
assert "report lists the very complex method, unmarked" '- Thing#old has a flog score of 61 (`app/models/thing.rb:2`)' "$(grep 'Thing#old' <<< "$report")"
assert "report lists changed code first" "Thing#call" "$(grep -m 1 -o 'Thing#[a-z]*' <<< "$report")"
assert "a change after a method's end doesn't mark it" '- Thing#last has a flog score of 30 (`app/models/thing.rb:10`)' "$(grep 'Thing#last' <<< "$report")"
contains "report says which items are findings" "Items marked (changed by this branch) are findings to fix in this branch" "$report"
assert "crapper scores only changed source" "crapper --use-existing-coverage app/hooks/thing.ts" "$(grep '^crapper' "$TOOL_LOG")"
assert "dryer scans the changed file's top-level folder" "dryer app" "$(grep '^dryer' "$TOOL_LOG")"
assert "rubycritic gets only changed Ruby" "app/models/thing.rb" "$(grep '^rubycritic' "$TOOL_LOG" | awk '{print $NF}')"
assert "rubycritic skips the Rails schema" "" "$(grep '^rubycritic' "$TOOL_LOG" | grep -o 'db/schema.rb')"
contains "rubycritic sees the noise config" "reek config present" "$(cat "$TOOL_LOG")"
assert "temporary reek config is removed" "no" "$([[ -e .reek.yml ]] && echo yes || echo no)"
assert "tool output folders are removed" "no" "$([[ -e .metrics ]] && echo yes || echo no)"
assert "working tree stays clean" "" "$(git status --porcelain)"
contains "run is recorded" '"event": "quality_signals_run"' "$(cat "$LEDGER")"
contains "run records the counts" '"crap_30_plus": 1, "crap_10_30": 1, "duplicates": 2, "ruby_flagged": 4, "changed_code_flags": 2' "$(cat "$LEDGER")"
contains "run records the machine name" '"host.name": "test-host"' "$(cat "$LEDGER")"

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
contains "the machine name falls back to the hostname" "\"host.name\": \"$(hostname -s)\"" "$(tail -n 1 "$LEDGER")"

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
