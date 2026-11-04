#!/usr/bin/env bash
set -uo pipefail

usage() {
  echo "usage: quality-signals.sh <base-ref>" >&2
  echo "       quality-signals.sh record <accepted> <dismissed>" >&2
  exit 2
}

HERE=$(cd "$(dirname "$0")" && pwd)
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/e2e"

emit() {
  local event=$1; shift
  local repo head payload key
  repo=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
  head=$(git rev-parse --short HEAD 2>/dev/null || echo unknown)
  payload=$(python3 - "$event" "$repo" "$head" "$(hostname -s)" "$@" <<'PY'
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
  printf '%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$payload" >> "$STATE_DIR/quality-signals.tsv"
  [[ ${QUALITY_SIGNALS_LEDGER:-on} == off ]] && return 0
  key=$(security find-generic-password -s honeycomb-agent-traces -w 2>/dev/null) || return 0
  [[ -n "$key" ]] || return 0
  curl -s -m 5 -X POST "https://api.eu1.honeycomb.io/1/events/workflow-ledger" \
    -H "X-Honeycomb-Team: $key" -H "Content-Type: application/json" -d "$payload" >/dev/null 2>&1 || true
}

[[ $# -ge 1 ]] || usage
if [[ $1 == record ]]; then
  [[ $# -eq 3 && $2 =~ ^[0-9]+$ && $3 =~ ^[0-9]+$ ]] || usage
  emit quality_signals_outcome "accepted=$2" "dismissed=$3"
  exit 0
fi
[[ $# -eq 1 ]] || usage
base=$1

top=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "quality-signals: not a git repository" >&2; exit 0; }
cd "$top" || exit 0
started=$(date +%s)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p .e2e
exclude=$(git rev-parse --git-path info/exclude)
mkdir -p "$(dirname "$exclude")"
grep -qxF .e2e/ "$exclude" 2>/dev/null || printf '.e2e/\n' >> "$exclude"
report=.e2e/quality-signals.md
: > "$work/not-run"

skipped() {
  case "$1" in
    */__tests__/*|*.test.*|*.spec.*|*_spec.rb|*_test.rb|*_test.go|test_*.py|spec/*|*/spec/*|test/*|*/test/*|tests/*|*/tests/*) return 0 ;;
    *.stories.*|*/stories/*|vendor/*|*/vendor/*|node_modules/*|*/node_modules/*) return 0 ;;
  esac
  head -n 5 "$1" 2>/dev/null | grep -qiE 'do not (modify|edit)|automatically generated|@generated'
}

if ! git diff --name-only --diff-filter=AM "$base"...HEAD > "$work/diff" 2>"$work/diff-error"; then
  printf '# Quality signals\n\nNot run: could not diff against `%s` (%s).\n' "$base" "$(head -n 1 "$work/diff-error")" > "$report"
  echo "$report"
  exit 0
fi
while read -r file; do
  [[ -f "$file" ]] || continue
  skipped "$file" && continue
  case "$file" in
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) echo "$file" >> "$work/scored"; echo "$file" >> "$work/js" ;;
    *.go|*.py) echo "$file" >> "$work/scored" ;;
    *.rb|*.rake) echo "$file" >> "$work/ruby" ;;
  esac
done < "$work/diff"
touch "$work/scored" "$work/js" "$work/ruby"

created=""
for dir in .metrics coverage; do
  [[ -e $dir ]] || created="$created $dir"
done

crap_high=0 crap_mid=0
if [[ -s "$work/scored" ]]; then
  if ! command -v crapper >/dev/null; then
    echo "crapper: not run (not installed)" >> "$work/not-run"
  else
    flags=()
    if [[ -n ${QUALITY_COVERAGE_CMD:-} ]]; then
      bash -c "$QUALITY_COVERAGE_CMD" > "$work/coverage.log" 2>&1 || echo "coverage: \`$QUALITY_COVERAGE_CMD\` failed, scores may show 0%" >> "$work/not-run"
      flags=(--use-existing-coverage)
    elif [[ -s "$work/js" && -f package.json ]] && grep -q '"test": *"[^"]*vitest' package.json; then
      if [[ -f pnpm-lock.yaml ]]; then runner=(pnpm run test); elif [[ -f yarn.lock ]]; then runner=(yarn test); else runner=(npm test --); fi
      major=$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)
      node_options=${NODE_OPTIONS:-}
      [[ $major -ge 25 && $node_options != *webstorage* ]] && node_options="$node_options --no-experimental-webstorage"
      NODE_OPTIONS=$node_options "${runner[@]}" --coverage.enabled --coverage.provider=v8 --coverage.reporter=lcov \
        --coverage.reportsDirectory=coverage --coverage.reportOnFailure > "$work/coverage.log" 2>&1 \
        || echo "coverage: tests failed, scores use the coverage that was written" >> "$work/not-run"
      flags=(--use-existing-coverage)
    fi
    xargs crapper ${flags[@]+"${flags[@]}"} < "$work/scored" > "$work/crapper.out" 2>&1
    awk '/^Function +Namespace/ {table=1; next} table && /^-+$/ {next} table && NF >= 5 {print}' "$work/crapper.out" > "$work/crap-rows"
    crap_high=$(awk '$NF + 0 >= 30' "$work/crap-rows" | wc -l | tr -d ' ')
    crap_mid=$(awk '$NF + 0 >= 10 && $NF + 0 < 30' "$work/crap-rows" | wc -l | tr -d ' ')
    if [[ ! -s "$work/crap-rows" ]]; then
      echo "crapper: ran but reported no functions ($(tail -n 1 "$work/crapper.out"))" >> "$work/not-run"
    elif ! awk '{sub(/%$/, "", $(NF-1)); if ($(NF-1) + 0 > 0) found=1} END {exit !found}' "$work/crap-rows"; then
      echo "crapper: every function shows 0% coverage, so coverage probably didn't run" >> "$work/not-run"
    fi
  fi
fi

duplicates=0
if [[ -s "$work/scored" ]]; then
  if ! command -v dryer >/dev/null; then
    echo "dryer: not run (not installed)" >> "$work/not-run"
  else
    cut -d/ -f1-2 "$work/scored" | sort -u | while read -r root; do [[ -e $root ]] && echo "$root"; done > "$work/roots"
    xargs dryer < "$work/roots" > "$work/dryer.out" 2>&1
    awk '/^DUPLICATE score=/ {score=$2; sub(/score=/, "", score); getline a; getline b; gsub(/^ +/, "", a); gsub(/^ +/, "", b); print score "\t" a "\t" b}' "$work/dryer.out" > "$work/pairs"
    while IFS=$'\t' read -r score left right; do
      left_file=${left%%:*} right_file=${right%%:*}
      skipped "$left_file" && continue
      skipped "$right_file" && continue
      grep -qxF "$left_file" "$work/scored" || grep -qxF "$right_file" "$work/scored" || continue
      printf -- '- score %s: `%s` and `%s`\n' "$score" "$left" "$right" >> "$work/dupes"
    done < "$work/pairs"
    [[ -f "$work/dupes" ]] && duplicates=$(wc -l < "$work/dupes" | tr -d ' ')
  fi
fi

ruby_flagged=0
if [[ -s "$work/ruby" ]]; then
  if ! command -v rubycritic >/dev/null; then
    echo "rubycritic: not run (not installed)" >> "$work/not-run"
  else
    reek_added=""
    if [[ ! -e .reek.yml ]]; then
      cp "$HERE/quality-signals.reek.yml" .reek.yml
      reek_added=1
    fi
    xargs rubycritic --no-browser --format console --path "$work/rubycritic" < "$work/ruby" > "$work/rubycritic.out" 2>&1
    [[ -n $reek_added ]] && rm -f .reek.yml
    awk '/^[A-Za-z0-9_:]+:$/ {name=$0; sub(/:$/, "", name)} /^ +Rating: +[DF]$/ {print "- " $2 ": `" name "`"}' "$work/rubycritic.out" > "$work/ruby-classes"
    awk '/\(HighComplexity\)/ {text=$0; sub(/^ *\* \(HighComplexity\) /, "", text); getline where; sub(/^ *- */, "", where); print $NF "\t- " text " (`" where "`)"}' "$work/rubycritic.out" \
      | sort -rn | cut -f2- > "$work/ruby-complex"
    ruby_flagged=$(cat "$work/ruby-classes" "$work/ruby-complex" | wc -l | tr -d ' ')
    grep -qE 'Rating:' "$work/rubycritic.out" || echo "rubycritic: ran but rated nothing ($(tail -n 1 "$work/rubycritic.out"))" >> "$work/not-run"
  fi
fi

for dir in $created; do rm -rf "$dir"; done
seconds=$(( $(date +%s) - started ))
scored_count=$(cat "$work/scored" "$work/ruby" | wc -l | tr -d ' ')

{
  echo "# Quality signals"
  echo
  echo "Base \`$base\`, head \`$(git rev-parse --short HEAD)\`: $scored_count changed source files, ${seconds}s. These are hints for the reviewers, not findings."
  if [[ -s "$work/crap-rows" ]]; then
    echo
    echo "## Risky functions (crapper)"
    echo
    echo "CRAP combines complexity with missing coverage. 30 or more is risky."
    echo
    awk '$NF + 0 >= 30 {printf "- `%s` in `%s`: CRAP %s, complexity %s, coverage %s\n", $1, $2, $NF, $(NF-2), $(NF-1)}' "$work/crap-rows" | head -n 15
    [[ $crap_high -eq 0 ]] && echo "- None at 30 or more."
    [[ $crap_mid -gt 0 ]] && echo "- $crap_mid more between 10 and 30."
  fi
  if [[ -s "$work/scored" ]] && command -v dryer >/dev/null; then
    echo
    echo "## Duplicates touching changed files (dryer)"
    echo
    if [[ -f "$work/dupes" ]]; then head -n 20 "$work/dupes"; else echo "- None."; fi
  fi
  if [[ -s "$work/ruby" ]] && command -v rubycritic >/dev/null; then
    echo
    echo "## Ruby (rubycritic)"
    echo
    if [[ $ruby_flagged -eq 0 ]]; then echo "- No D or F classes and no high-complexity methods."; fi
    cat "$work/ruby-classes"
    head -n 15 "$work/ruby-complex"
  fi
  if [[ -s "$work/not-run" ]]; then
    echo
    echo "## Not run or incomplete"
    echo
    sed 's/^/- /' "$work/not-run"
  fi
} > "$report"

not_run=$(cut -d: -f1 "$work/not-run" | sort -u | paste -sd, -)
emit quality_signals_run "changed_files=$scored_count" "crap_30_plus=$crap_high" "crap_10_30=$crap_mid" \
  "duplicates=$duplicates" "ruby_flagged=$ruby_flagged" "not_run=${not_run:-none}" "seconds=$seconds"
echo "$report"
exit 0
