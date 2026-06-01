"""Shared pytest fixtures.

`fresh_db` gives every test its own sqlite file in a tmp dir.
`db_with_1k_notes` seeds 1000 notes for the perf benchmark in test_search.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from note_cli import storage


@pytest.fixture
def fresh_db(tmp_path: Path) -> sqlite3.Connection:
    return storage.connect(tmp_path / "notes.db")


@pytest.fixture
def db_with_1k_notes(tmp_path: Path) -> sqlite3.Connection:
    conn = storage.connect(tmp_path / "notes.db")
    # Seed 1000 distinct notes plus 5 deliberate duplicates to exercise find_duplicates.
    for i in range(1000):
        storage.add_note(conn, f"unique note number {i}")
    for body in ["dup-a", "dup-b", "dup-c", "dup-d", "dup-e"]:
        storage.add_note(conn, body)
        storage.add_note(conn, body)
    return conn
