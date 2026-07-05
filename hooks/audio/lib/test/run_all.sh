#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0
for t in "$DIR"/*.test.sh; do
    echo "== $(basename "$t") =="
    bash "$t" || fail=1
done
echo "========================"
[ "$fail" -eq 0 ] && echo "ALL PASS" || { echo "SOME FAILED"; exit 1; }
