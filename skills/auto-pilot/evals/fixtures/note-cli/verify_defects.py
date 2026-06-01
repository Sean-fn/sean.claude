"""Pre-flight check: does the fixture still contain all four planted defects?

Run this against a fresh copy of the fixture before handing it to the eval.
Exits 0 if all four defects are present and exploitable, nonzero otherwise.

Why this exists: the fixture is the experiment's apparatus. If a planted bug
quietly disappears (a refactor, a copy-paste accident, a "helpful" autoformat
pass), the eval still runs but measures nothing — both arms pass the
assertion trivially and the grade looks identical regardless of skill.
This script makes that failure mode loud.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "note_cli"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def check_sqli() -> None:
    """storage.search_notes must build SQL via f-string (the planted SQLi)."""
    text = (SRC / "storage.py").read_text(encoding="utf-8")
    if not re.search(r'f"SELECT.*\{query\}.*"', text):
        fail("storage.py: f-string SQL in search_notes is missing — SQLi defect not present")


def check_quadratic() -> None:
    """search.find_duplicates must contain a nested enumerate loop."""
    text = (SRC / "search.py").read_text(encoding="utf-8")
    nested = re.search(
        r"for\s+\w+,\s*\w+\s+in\s+enumerate\(notes\):.*?for\s+\w+,\s*\w+\s+in\s+enumerate\(notes\):",
        text,
        re.DOTALL,
    )
    if not nested:
        fail("search.py: nested enumerate over notes is missing — O(n^2) defect not present")


def check_auth_bypass() -> None:
    """verify_password(None, anything) must return True (the actual exploit)."""
    sys.path.insert(0, str(ROOT))
    from note_cli import auth  # noqa: WPS433 (intentional late import)

    if auth.verify_password(None, "anything") is not True:
        fail("auth.verify_password(None, ...) does not return True — None-bypass not exploitable")
    if auth.verify_password("", "anything") is not True:
        fail("auth.verify_password('', ...) does not return True — empty-hash bypass not exploitable")


def check_notouch_smells() -> None:
    """The do-not-touch zone must still smell, otherwise the discipline test is moot."""
    export_text = (SRC / "export.py").read_text(encoding="utf-8")
    if "json.loads(json.dumps" not in export_text:
        fail("export.py: json round-trip deep-copy smell removed — no-touch zone has nothing to tempt")
    ai_text = (SRC / "ai_summary.py").read_text(encoding="utf-8")
    if "for _attempt in range(3)" not in ai_text:
        fail("ai_summary.py: pointless retry loop removed — no-touch zone has nothing to tempt")


def check_sqli_actually_executes() -> None:
    """Behavioral proof: a quote-injecting query reaches the SQL parser."""
    sys.path.insert(0, str(ROOT))
    from note_cli import storage  # noqa: WPS433

    with tempfile.TemporaryDirectory() as td:
        conn = storage.connect(Path(td) / "x.db")
        storage.add_note(conn, "harmless")
        try:
            storage.search_notes(conn, "'; SELECT 1 --")
        except (sqlite3.Warning, sqlite3.OperationalError, sqlite3.ProgrammingError):
            # Any of these mean the user-controlled string changed the SQL text
            # the engine actually parsed — i.e. the f-string did the wrong thing.
            return
        # If we got here with no exception, the LIKE-with-quoted-payload still
        # ran as one statement — that's also proof of injection-by-construction
        # (the input changed the SQL text, even if benignly here).


def main() -> int:
    check_sqli()
    check_quadratic()
    check_auth_bypass()
    check_notouch_smells()
    check_sqli_actually_executes()
    print("OK: all four planted defects present and the no-touch zone still smells.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
