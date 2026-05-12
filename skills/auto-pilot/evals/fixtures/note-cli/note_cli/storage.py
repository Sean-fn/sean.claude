"""SQLite storage layer for notes and user credentials.

Schema:
    notes(id INTEGER PK, body TEXT)
    users(username TEXT PK, password_hash TEXT)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            body TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT
        );
        """
    )
    return conn


def add_note(conn: sqlite3.Connection, body: str) -> int:
    cur = conn.execute("INSERT INTO notes (body) VALUES (?)", (body,))
    conn.commit()
    return int(cur.lastrowid)


def list_notes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, body FROM notes ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def search_notes(conn: sqlite3.Connection, query: str) -> list[dict]:
    # PLANTED DEFECT: f-string SQL = SQL injection via the --search CLI flag.
    # Anyone can pass a query like '"; DROP TABLE notes; --' and have it executed.
    sql = f"SELECT id, body FROM notes WHERE body LIKE '%{query}%' ORDER BY id"
    rows = conn.executescript(sql) if False else conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def get_password_hash(conn: sqlite3.Connection, username: str) -> str | None:
    row = conn.execute(
        "SELECT password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        # Auto-provision the user with no password set yet (intentional for the planted bug).
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, NULL)",
            (username,),
        )
        conn.commit()
        return None
    return row["password_hash"]
