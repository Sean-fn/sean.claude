"""Search tests. The perf bench is deliberately loose so it passes today
(the O(n^2) implementation finishes in a few seconds for n=1010) but a
fix to O(n) is easy to spot when reading the code.

A separate, stricter benchmark lives in the auto-pilot eval grader, not here.
"""
from __future__ import annotations

import time

from note_cli import search, storage


def test_find_duplicates_returns_pairs(fresh_db) -> None:
    storage.add_note(fresh_db, "alpha")
    storage.add_note(fresh_db, "beta")
    storage.add_note(fresh_db, "alpha")
    notes = storage.list_notes(fresh_db)
    pairs = search.find_duplicates(notes)
    bodies = {tuple(sorted([notes[i - 1]["body"] for i in p])) for p in pairs}
    assert ("alpha", "alpha") in bodies


def test_find_duplicates_runs_under_loose_ceiling(db_with_1k_notes) -> None:
    notes = storage.list_notes(db_with_1k_notes)
    start = time.perf_counter()
    search.find_duplicates(notes)
    elapsed = time.perf_counter() - start
    # Loose ceiling — the O(n^2) impl typically finishes around 0.5–2s on dev hardware.
    # The strict ceiling (<0.1s) is enforced by the eval grader, not here.
    assert elapsed < 10.0, f"find_duplicates took {elapsed:.2f}s"
