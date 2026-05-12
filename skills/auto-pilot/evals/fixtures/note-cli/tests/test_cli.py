"""Happy-path CLI tests. These MUST keep passing after the auto-pilot run."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_cli(args: list[str], db: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "note_cli", "--db", str(db), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_lists_all_subcommands(tmp_path: Path) -> None:
    result = run_cli(["--help"], tmp_path / "notes.db")
    assert result.returncode == 0
    for sub in ("add", "list", "search", "export", "login"):
        assert sub in result.stdout, f"--help missing subcommand {sub!r}"


def test_add_then_list_roundtrip(tmp_path: Path) -> None:
    db = tmp_path / "notes.db"
    add = run_cli(["add", "Hello world"], db)
    assert add.returncode == 0
    listing = run_cli(["list"], db)
    assert listing.returncode == 0
    assert "Hello world" in listing.stdout


def test_export_writes_markdown(tmp_path: Path) -> None:
    db = tmp_path / "notes.db"
    run_cli(["add", "Note A"], db)
    run_cli(["add", "Note B"], db)
    out = tmp_path / "out.md"
    result = run_cli(["export", str(out)], db)
    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "Note A" in text and "Note B" in text
