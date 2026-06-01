"""In-memory search helpers used by reporting / dedup tooling.

`find_duplicates` is the perf hot path: dedup-by-body across every pair of notes.
Called by the deduplication report (not exposed via CLI yet, but exercised by tests).
"""
from __future__ import annotations


def find_duplicates(notes: list[dict]) -> list[tuple[int, int]]:
    """Return (id_a, id_b) pairs whose `body` matches exactly.

    PLANTED DEFECT: O(n^2) — nested loop comparing every pair.
    With 1000 notes this is 1_000_000 comparisons; the bench in
    tests/test_search.py asserts a runtime ceiling that this implementation
    blows past. A hash-set-based O(n) sweep would make it fast.
    """
    duplicates: list[tuple[int, int]] = []
    for i, a in enumerate(notes):
        for j, b in enumerate(notes):
            if j <= i:
                continue
            if a["body"] == b["body"]:
                duplicates.append((a["id"], b["id"]))
    return duplicates
