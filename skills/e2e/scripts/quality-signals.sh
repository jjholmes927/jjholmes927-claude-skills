#!/usr/bin/env bash
set -uo pipefail

usage() {
  echo "usage: quality-signals.sh <base-ref>" >&2
  echo "       quality-signals.sh record <accepted> <dismissed>" >&2
  exit 2
}

HERE=$(cd "$(dirname "$0")" && pwd)
. "$HERE/ledger.sh"

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
  head -n 5 "$1" 2>/dev/null | grep -qiE 'do not (modify|edit)|auto(matically)?[- ]generated|@generated'
}

touches() {
  local file=${1%%:*} range=${1#*:}
  awk -F'\t' -v file="$file" -v from="${range%-*}" -v to="${range#*-}" \
    '$1 == file && $2 <= to && $3 >= from {found = 1} END {exit !found}' "$work/changed-lines"
}

method_changed() {
  local file=${1%%:*} start=${1##*:} end
  end=$(awk -v start="$start" '
    NR == start {match($0, /^[[:space:]]*/); closing = "^" substr($0, 1, RLENGTH) "end([[:space:]]|$)"}
    NR > start && $0 ~ closing {print NR; found = 1; exit}
    END {if (!found) print start}
  ' "$file" 2>/dev/null) || return 1
  touches "$file:$start-$end"
}

changed_first() {
  grep -F "$mark" "$1"
  grep -vF "$mark" "$1" | head -n "$2"
}

available() {
  command -v "$1" >/dev/null && return 0
  echo "$1: not run (not installed)" >> "$work/not-run"
  return 1
}

if ! git diff --name-only --diff-filter=AM "$base"...HEAD > "$work/diff" 2>"$work/diff-error"; then
  printf '# Quality signals\n\nNot run: could not diff against `%s` (%s).\n' "$base" "$(head -n 1 "$work/diff-error")" > "$report"
  echo "$report"
  exit 0
fi
has_js=""
: > "$work/scored"
: > "$work/ruby"
while read -r file; do
  [[ -f "$file" ]] || continue
  skipped "$file" && continue
  case "$file" in
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) echo "$file" >> "$work/scored"; has_js=1 ;;
    *.go|*.py) echo "$file" >> "$work/scored" ;;
    *.rb|*.rake) echo "$file" >> "$work/ruby" ;;
  esac
done < "$work/diff"
git diff -U0 --no-color "$base"...HEAD | awk '
  /^\+\+\+ b\// {file = substr($0, 7)}
  /^@@ / {split(substr($3, 2), range, ","); count = (range[2] == "") ? 1 : range[2]; print file "\t" range[1] "\t" range[1] + (count > 0 ? count - 1 : 0)}
' > "$work/changed-lines"
mark="(changed by this branch)"

created=""
for path in .metrics coverage .reek.yml; do
  [[ -e $path ]] || created="$created $path"
done

crap_high=0 crap_mid=0 crapper_ran=""
if [[ -s "$work/scored" ]] && available crapper; then
  crapper_ran=1
  coverage_flag=""
  if [[ -n ${QUALITY_COVERAGE_CMD:-} ]]; then
    bash -c "$QUALITY_COVERAGE_CMD" > "$work/coverage.log" 2>&1 || echo "coverage: \`$QUALITY_COVERAGE_CMD\` failed, scores may show 0%" >> "$work/not-run"
    coverage_flag=--use-existing-coverage
  elif [[ -n $has_js && -f package.json ]] && grep -q '"test": *"[^"]*vitest' package.json; then
    if [[ -f pnpm-lock.yaml ]]; then runner="pnpm run test"; elif [[ -f yarn.lock ]]; then runner="yarn test"; else runner="npm test --"; fi
    includes=$(grep -E '\.(ts|tsx|js|jsx|mjs|cjs)$' "$work/scored" | sed 's/^/--coverage.include=/' | paste -sd' ' -)
    $runner --changed "$base" $includes --coverage.enabled --coverage.provider=v8 --coverage.reporter=lcovonly \
      --coverage.reportsDirectory=coverage --coverage.reportOnFailure > "$work/coverage.log" 2>&1 \
      || echo "coverage: tests failed, scores use the coverage that was written" >> "$work/not-run"
    coverage_flag=--use-existing-coverage
  fi
  xargs crapper $coverage_flag < "$work/scored" > "$work/crapper.out" 2>&1
  awk '/^Function +Namespace/ {table=1; next} table && /^-+$/ {next} table && NF >= 5 {print}' "$work/crapper.out" > "$work/crap-rows"
  awk '$NF + 0 >= 30' "$work/crap-rows" > "$work/crap-high"
  crap_high=$(wc -l < "$work/crap-high" | tr -d ' ')
  crap_mid=$(awk '$NF + 0 >= 10 && $NF + 0 < 30' "$work/crap-rows" | wc -l | tr -d ' ')
  if [[ ! -s "$work/crap-rows" ]]; then
    echo "crapper: ran but reported no functions ($(tail -n 1 "$work/crapper.out"))" >> "$work/not-run"
  elif ! awk '{sub(/%$/, "", $(NF-1)); if ($(NF-1) + 0 > 0) found=1} END {exit !found}' "$work/crap-rows"; then
    echo "crapper: every function shows 0% coverage, so coverage probably didn't run" >> "$work/not-run"
  fi
fi

duplicates=0 dryer_ran=""
: > "$work/dupes"
if [[ -s "$work/scored" ]] && available dryer; then
  dryer_ran=1
  cut -d/ -f1 "$work/scored" | sort -u > "$work/roots"
  xargs dryer < "$work/roots" > "$work/dryer.out" 2>&1
  awk '/^DUPLICATE score=/ {score=$2; sub(/score=/, "", score); getline a; getline b; gsub(/^ +/, "", a); gsub(/^ +/, "", b); print score "\t" a "\t" b}' "$work/dryer.out" > "$work/pairs"
  while IFS=$'\t' read -r score left right; do
    left_file=${left%%:*} right_file=${right%%:*}
    grep -qxF "$left_file" "$work/scored" || grep -qxF "$right_file" "$work/scored" || continue
    skipped "$left_file" && continue
    skipped "$right_file" && continue
    suffix=""
    if touches "$left" || touches "$right"; then suffix=" $mark"; fi
    printf -- '- score %s: `%s` and `%s`%s\n' "$score" "$left" "$right" "$suffix" >> "$work/dupes"
  done < "$work/pairs"
  duplicates=$(wc -l < "$work/dupes" | tr -d ' ')
fi

ruby_flagged=0 ruby_ran=""
if [[ -s "$work/ruby" ]] && available rubycritic; then
  ruby_ran=1
  [[ -e .reek.yml ]] || cp "$HERE/quality-signals.reek.yml" .reek.yml
  xargs rubycritic --no-browser --format console --churn-after "$(date +%F)" --path "$work/rubycritic" < "$work/ruby" > "$work/rubycritic.out" 2>&1
  awk '/^[A-Za-z0-9_:]+:$/ {name=$0; sub(/:$/, "", name)} /^ +Rating: +[DF]$/ {print "- " $2 ": `" name "`"}' "$work/rubycritic.out" > "$work/ruby-classes"
  awk '/\((Very)?HighComplexity\)/ {text=$0; sub(/^ *\* \((Very)?HighComplexity\) /, "", text); getline where; sub(/^ *- */, "", where); print $NF "\t" text "\t" where}' "$work/rubycritic.out" \
    | sort -rn | while IFS=$'\t' read -r _ text where; do
    suffix=""
    if method_changed "$where"; then suffix=" $mark"; fi
    printf -- '- %s (`%s`)%s\n' "$text" "$where" "$suffix"
  done > "$work/ruby-complex"
  ruby_flagged=$(cat "$work/ruby-classes" "$work/ruby-complex" | wc -l | tr -d ' ')
  grep -qE 'Rating:' "$work/rubycritic.out" || echo "rubycritic: ran but rated nothing ($(tail -n 1 "$work/rubycritic.out"))" >> "$work/not-run"
fi

for path in $created; do rm -rf "$path"; done
seconds=$(( $(date +%s) - started ))
scored_count=$(cat "$work/scored" "$work/ruby" | wc -l | tr -d ' ')
changed_flags=$(cat "$work/dupes" "$work/ruby-complex" 2>/dev/null | grep -cF "$mark")

{
  echo "# Quality signals"
  echo
  echo "Base \`$base\`, head \`$(git rev-parse --short HEAD)\`: $scored_count changed source files, ${seconds}s. Items marked $mark are findings to fix in this branch. crapper can't tell which functions changed, so check its list against the diff. Everything else is a hint."
  if [[ -n $crapper_ran && -s "$work/crap-rows" ]]; then
    echo
    echo "## Risky functions (crapper)"
    echo
    echo "CRAP combines complexity with missing coverage. 30 or more is risky."
    echo
    awk '{printf "- `%s` in `%s`: CRAP %s, complexity %s, coverage %s\n", $1, $2, $NF, $(NF-2), $(NF-1)}' "$work/crap-high" | head -n 15
    [[ $crap_high -eq 0 ]] && echo "- None at 30 or more."
    [[ $crap_mid -gt 0 ]] && echo "- $crap_mid more between 10 and 30."
  fi
  if [[ -n $dryer_ran ]]; then
    echo
    echo "## Duplicates touching changed files (dryer)"
    echo
    if [[ -s "$work/dupes" ]]; then changed_first "$work/dupes" 20; else echo "- None."; fi
  fi
  if [[ -n $ruby_ran ]]; then
    echo
    echo "## Ruby (rubycritic)"
    echo
    [[ $ruby_flagged -eq 0 ]] && echo "- No D or F classes and no high-complexity methods."
    cat "$work/ruby-classes"
    changed_first "$work/ruby-complex" 15
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
  "duplicates=$duplicates" "ruby_flagged=$ruby_flagged" "changed_code_flags=$changed_flags" "not_run=${not_run:-none}" "seconds=$seconds"
echo "$report"
exit 0
