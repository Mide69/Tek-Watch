#!/usr/bin/env bash
# One run of every suite, printed as a single block worth screenshotting.
#
# Each suite is run on its own because they use different runners, then the
# counts are added up here. Exits non-zero if anything failed, so this is a
# check you can trust rather than a report that always looks green.
#
#   bash scripts/test-summary.sh

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

pass_total=0
fail_total=0
rows=""

# pytest -q ends with a line like "471 passed in 4.63s" or
# "1 failed, 290 passed in 22.68s".
run_pytest() {
    local dir="$1" out p f
    out=$(cd "$dir" && python -m pytest -q 2>&1 | tail -1)
    p=$(printf '%s' "$out" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+') || p=0
    f=$(printf '%s' "$out" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+') || f=0
    printf -v rows '%s  %-18s %5s passed %s\n' "$rows" "$dir" "${p:-0}" \
        "$( [ "${f:-0}" -gt 0 ] && printf '%s failed' "$f" )"
    pass_total=$(( pass_total + ${p:-0} ))
    fail_total=$(( fail_total + ${f:-0} ))
}

# jest prints "Tests:  88 passed, 88 total" (and "N failed," before it if any).
run_jest() {
    local dir="$1" out p f
    out=$(cd "$dir" && npx jest 2>&1 | grep -E '^Tests:')
    p=$(printf '%s' "$out" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+') || p=0
    f=$(printf '%s' "$out" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+') || f=0
    printf -v rows '%s  %-18s %5s passed %s\n' "$rows" "$dir" "${p:-0}" \
        "$( [ "${f:-0}" -gt 0 ] && printf '%s failed' "$f" )"
    pass_total=$(( pass_total + ${p:-0} ))
    fail_total=$(( fail_total + ${f:-0} ))
}

echo "Running all four suites. This takes about a minute."
echo

run_pytest api
run_pytest agent
run_pytest ingest-consumer
run_jest   dashboard

echo "TekWatch test suite"
echo "commit $(git rev-parse --short HEAD)  ·  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo
printf '%s' "$rows"
echo "  ----------------------------------------"
printf '  %-18s %5s passed, %s failed\n' "TOTAL" "$pass_total" "$fail_total"
echo

[ "$fail_total" -eq 0 ] || exit 1
