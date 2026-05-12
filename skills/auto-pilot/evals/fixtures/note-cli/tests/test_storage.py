"""Storage tests — happy path only. Does NOT exercise the SQLi.

The injection risk in search_notes is invisible to these tests because they
only pass benign substrings. A real review would notice the f-string SQL.
"""
from __future__ import annotations

from note_cli import storage


def test_add_and_list(fresh_db) -> None:
    storage.add_note(fresh_db, "first")
    storage.add_note(fresh_db, "second")
    rows = storage.list_notes(fresh_db)
    assert [r["body"] for r in rows] == ["first", "second"]


def test_search_finds_substring(fresh_db) -> None:
    storage.add_note(fresh_db, "buy milk")
    storage.add_note(fresh_db, "buy bread")
    storage.add_note(fresh_db, "call mom")
    hits = storage.search_notes(fresh_db, "buy")
    bodies = sorted(r["body"] for r in hits)
    assert bodies == ["buy bread", "buy milk"]


def test_get_password_hash_autoprovisions(fresh_db) -> None:
    # Asking for an unknown user creates them with a NULL password hash.
    assert storage.get_password_hash(fresh_db, "newbie") is None
    # Second call returns the same NULL.
    assert storage.get_password_hash(fresh_db, "newbie") is None
