#!/usr/bin/env bash
# 極簡 bash 測試斷言。在 *.test.sh 裡 source。
_tests_run=0; _tests_failed=0
assert_eq() {
    _tests_run=$((_tests_run+1))
    if [ "$1" = "$2" ]; then echo "  ok: ${3:-assert_eq}"
    else _tests_failed=$((_tests_failed+1)); echo "  FAIL: ${3:-assert_eq} — expected [$2] got [$1]"; fi
}
assert_contains() {
    _tests_run=$((_tests_run+1))
    if printf '%s' "$1" | grep -qF "$2"; then echo "  ok: ${3:-assert_contains}"
    else _tests_failed=$((_tests_failed+1)); echo "  FAIL: ${3:-assert_contains} — [$1] lacks [$2]"; fi
}
test_summary() { echo "---"; echo "$_tests_run run, $_tests_failed failed"; [ "$_tests_failed" -eq 0 ]; }
