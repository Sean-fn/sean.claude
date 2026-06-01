"""argparse front-end for note-cli."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from note_cli import auth, export, search, storage

DEFAULT_DB = Path.home() / ".note_cli" / "notes.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="note_cli", description="Tiny notes CLI")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to sqlite db")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a new note")
    p_add.add_argument("body", help="Note body")

    sub.add_parser("list", help="List all notes")

    p_search = sub.add_parser("search", help="Search notes by substring")
    p_search.add_argument("query", help="Search query")

    p_export = sub.add_parser("export", help="Export notes to markdown")
    p_export.add_argument("out", type=Path, help="Output file")

    p_login = sub.add_parser("login", help="Log in as a user")
    p_login.add_argument("username", help="Username")
    p_login.add_argument("--password", default="", help="Password (empty to test)")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = storage.connect(args.db)

    if args.cmd == "add":
        storage.add_note(conn, args.body)
        print(f"Added: {args.body}")
        return 0

    if args.cmd == "list":
        for note in storage.list_notes(conn):
            print(f"{note['id']}: {note['body']}")
        return 0

    if args.cmd == "search":
        # Hot-path search: substring across all notes.
        rows = storage.search_notes(conn, args.query)
        for note in rows:
            print(f"{note['id']}: {note['body']}")
        return 0

    if args.cmd == "export":
        notes = storage.list_notes(conn)
        export.write_markdown(notes, args.out)
        print(f"Exported {len(notes)} notes to {args.out}")
        return 0

    if args.cmd == "login":
        stored = storage.get_password_hash(conn, args.username)
        if auth.verify_password(stored, args.password):
            print(f"Welcome, {args.username}!")
            return 0
        print("Login failed.", file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
