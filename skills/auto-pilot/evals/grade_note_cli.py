"""Post-run grader for the note-cli eval.

Usage:
    python grade_note_cli.py --repo <post-run repo> --baseline <pristine fixture> \\
                             --state <path to state.json or "">              \\
                             --out <path to grading.json>

Splits the 12 assertions into two buckets:

* **Programmatic (7)** — checked here by importing the post-run code and
  diffing against the pristine baseline.
* **State-derived (5)** — checked by reading the `auto-pilot` state.json the
  with-skill arm produces. The baseline arm has no state.json, so for it we
  emit `passed=False` with `evidence="no state.json (expected for baseline)"`.

The schema matches what `scripts/aggregate_benchmark.py` consumes:

    {
      "summary": {"passed": N, "failed": M, "total": N+M, "pass_rate": ...},
      "expectations": [{"text": "...", "passed": bool, "evidence": "..."}]
    }
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import subprocess
import sys
import sqlite3
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


# --------------------------- expectation helpers ---------------------------

@dataclass
class Expectation:
    text: str
    passed: bool
    evidence: str


def emit(expectations: list[Expectation], text: str, passed: bool, evidence: str) -> None:
    expectations.append(Expectation(text=text, passed=passed, evidence=evidence))


# --------------------------- programmatic checks ---------------------------

def import_module_from(repo: Path, dotted: str):
    """Import note_cli.<...> from a specific repo without polluting sys.modules."""
    sys.path.insert(0, str(repo))
    # Force fresh import in case a prior call cached the baseline copy.
    for k in [m for m in sys.modules if m == dotted or m.startswith(dotted + ".") or m.startswith("note_cli")]:
        del sys.modules[k]
    try:
        return importlib.import_module(dotted)
    finally:
        sys.path.remove(str(repo))


def check_auth_bypass_fixed(repo: Path, exp: list[Expectation]) -> None:
    """#5: verify_password(None, anything) must now return False."""
    try:
        auth = import_module_from(repo, "note_cli.auth")
        none_result = auth.verify_password(None, "anything")
        empty_result = auth.verify_password("", "anything")
        passed = none_result is False and empty_result is False
        emit(exp, "verify_password(None, ...) returns False (None-hash bypass fixed)",
             passed, f"None→{none_result!r}, ''→{empty_result!r}")
    except Exception as e:  # noqa: BLE001
        emit(exp, "verify_password(None, ...) returns False (None-hash bypass fixed)",
             False, f"import/call failed: {e!r}")


def check_sqli_fixed(repo: Path, exp: list[Expectation]) -> None:
    """#6: storage.search_notes must no longer build SQL via f-string."""
    text = (repo / "note_cli" / "storage.py").read_text(encoding="utf-8")
    has_fstring_sql = bool(re.search(r'f["\'].*SELECT.*\{[^}]+\}.*["\']', text, re.IGNORECASE))
    # Behavioral check: a malicious payload should not blow up or alter SQL text.
    behavioral_ok = False
    behavioral_evidence = ""
    try:
        storage = import_module_from(repo, "note_cli.storage")
        with tempfile.TemporaryDirectory() as td:
            conn = storage.connect(Path(td) / "x.db")
            storage.add_note(conn, "harmless")
            try:
                rows = storage.search_notes(conn, "'; DROP TABLE notes; --")
                # Should return [] (no notes match that literal substring) without raising.
                behavioral_ok = isinstance(rows, list)
                behavioral_evidence = f"search returned {len(rows)} rows, no exception"
            except (sqlite3.ProgrammingError, sqlite3.Warning, sqlite3.OperationalError) as e:
                behavioral_ok = False
                behavioral_evidence = f"injection payload still alters SQL: {e!r}"
    except Exception as e:  # noqa: BLE001
        behavioral_evidence = f"could not run behavioral check: {e!r}"

    passed = (not has_fstring_sql) and behavioral_ok
    emit(exp, "search_notes is parametrised (no f-string SQL, injection payload returns []",
         passed, f"f-string-sql-present={has_fstring_sql}; {behavioral_evidence}")


def check_perf_fixed(repo: Path, exp: list[Expectation], threshold_seconds: float = 0.1) -> None:
    """#7: find_duplicates over 1010 notes must finish under threshold."""
    try:
        storage = import_module_from(repo, "note_cli.storage")
        search = import_module_from(repo, "note_cli.search")
        with tempfile.TemporaryDirectory() as td:
            conn = storage.connect(Path(td) / "x.db")
            for i in range(1000):
                storage.add_note(conn, f"unique note number {i}")
            for body in ("dup-a", "dup-b", "dup-c", "dup-d", "dup-e"):
                storage.add_note(conn, body)
                storage.add_note(conn, body)
            notes = storage.list_notes(conn)
            start = time.perf_counter()
            pairs = search.find_duplicates(notes)
            elapsed = time.perf_counter() - start
        passed = elapsed < threshold_seconds and len(pairs) >= 5
        emit(exp,
             f"find_duplicates on 1010 notes finishes in <{threshold_seconds}s (was O(n^2))",
             passed,
             f"elapsed={elapsed:.4f}s, pairs_found={len(pairs)}")
    except Exception as e:  # noqa: BLE001
        emit(exp, f"find_duplicates on 1010 notes finishes in <{threshold_seconds}s",
             False, f"check failed: {e!r}")


def check_no_touch(repo: Path, baseline: Path, filename: str, exp: list[Expectation]) -> None:
    """#10/#11: a do-not-touch-zone file must be byte-identical to the baseline."""
    a = (baseline / "note_cli" / filename).read_bytes()
    b_path = repo / "note_cli" / filename
    if not b_path.exists():
        emit(exp, f"note_cli/{filename} unchanged (do-not-touch zone)",
             False, "file deleted from repo")
        return
    b = b_path.read_bytes()
    same = (a == b)
    if same:
        emit(exp, f"note_cli/{filename} unchanged (do-not-touch zone)",
             True, f"{len(a)} bytes, byte-identical to baseline")
        return
    # Show a small diff for evidence.
    diff = subprocess.run(
        ["diff", "-u", str(baseline / "note_cli" / filename), str(b_path)],
        capture_output=True, text=True, check=False,
    ).stdout
    snippet = "\n".join(diff.splitlines()[:20])
    emit(exp, f"note_cli/{filename} unchanged (do-not-touch zone)",
         False, f"file modified; first 20 diff lines:\n{snippet}")


def check_pytest_and_help(repo: Path, exp: list[Expectation]) -> None:
    """#12: pytest exits 0 AND --help lists all 5 subcommands."""
    venv = repo / ".venv"
    py = venv / "bin" / "python"
    if not py.exists():
        # Best-effort: build a venv so the assertion is reproducible.
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=False)
        subprocess.run([str(py), "-m", "pip", "install", "-q", "pytest", "-e", str(repo)],
                       check=False, cwd=repo)

    pytest_proc = subprocess.run([str(py), "-m", "pytest", "-q"],
                                 capture_output=True, text=True, check=False, cwd=repo)
    help_proc = subprocess.run([str(py), "-m", "note_cli", "--help"],
                               capture_output=True, text=True, check=False, cwd=repo)

    pytest_ok = pytest_proc.returncode == 0
    help_ok = help_proc.returncode == 0 and all(
        sub in help_proc.stdout for sub in ("add", "list", "search", "export", "login")
    )
    passed = pytest_ok and help_ok
    evidence = (
        f"pytest rc={pytest_proc.returncode}, help rc={help_proc.returncode}, "
        f"all-subcommands-listed={help_ok}"
    )
    emit(exp, "pytest exits 0 and --help lists add/list/search/export/login", passed, evidence)


# --------------------------- state-derived checks ---------------------------

def check_state(state: dict[str, Any] | None, exp: list[Expectation]) -> None:
    """#1–#4, #8, #9: read auto-pilot state.json. Baseline has none."""
    if state is None:
        for text in (
            "state.json exists with stage=='D'",
            "execution_mode == 'phase-by-phase' (Mode 2 selected)",
            "history shows >=1 transition into stage C and >=3 phases done",
            "plan file at state.plan_path has >=4 implementation phases",
            "/security-review invoked at least once during Mode 2",
            "/optimize invoked at least once during Mode 2",
        ):
            emit(exp, text, False, "no state.json (expected for baseline arm)")
        return

    stage = state.get("stage")
    emit(exp, "state.json exists with stage=='D'",
         stage == "D", f"stage={stage!r}")

    mode = state.get("execution_mode")
    emit(exp, "execution_mode == 'phase-by-phase' (Mode 2 selected)",
         mode == "phase-by-phase", f"execution_mode={mode!r}")

    history = state.get("history", []) or []
    phases = state.get("phases", []) or []
    c_transitions = sum(1 for h in history if h.get("to") == "C")
    done_phases = sum(1 for p in phases if p.get("status") == "done")
    emit(exp, "history shows >=1 transition into stage C and >=3 phases done",
         c_transitions >= 1 and done_phases >= 3,
         f"C-transitions={c_transitions}, done-phases={done_phases}")

    plan_path = state.get("plan_path", "")
    plan_phase_count = 0
    if plan_path and Path(plan_path).exists():
        plan_text = Path(plan_path).read_text(encoding="utf-8")
        plan_phase_count = len(re.findall(r"^##\s+Phase\b", plan_text, re.MULTILINE))
    emit(exp, "plan file at state.plan_path has >=4 implementation phases",
         plan_phase_count >= 4, f"plan_path={plan_path!r}, phase-headings={plan_phase_count}")

    # Review routing — accept either history entries or a flat reviews list.
    review_records = (
        [h.get("review") for h in history if h.get("review")]
        + state.get("reviews", [])
    )
    review_blob = " ".join(str(r) for r in review_records)
    emit(exp, "/security-review invoked at least once during Mode 2",
         "security-review" in review_blob,
         f"review records: {review_records!r}")
    emit(exp, "/optimize invoked at least once during Mode 2",
         "optimize" in review_blob,
         f"review records: {review_records!r}")


# --------------------------- main ---------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path,
                    help="Post-run repo (the agent's modified copy of note-cli)")
    ap.add_argument("--baseline", required=True, type=Path,
                    help="Pristine fixture path (for byte-diffing the no-touch zone)")
    ap.add_argument("--state", default="", type=str,
                    help="Path to auto-pilot state.json. Empty for baseline arm.")
    ap.add_argument("--out", required=True, type=Path,
                    help="Where to write grading.json")
    ap.add_argument("--perf-threshold", default=0.1, type=float,
                    help="Seconds; find_duplicates must finish under this on n=1010")
    args = ap.parse_args()

    expectations: list[Expectation] = []

    state: dict[str, Any] | None = None
    if args.state:
        sp = Path(args.state)
        if sp.exists():
            state = json.loads(sp.read_text(encoding="utf-8"))
    check_state(state, expectations)

    check_auth_bypass_fixed(args.repo, expectations)
    check_sqli_fixed(args.repo, expectations)
    check_perf_fixed(args.repo, expectations, args.perf_threshold)
    check_no_touch(args.repo, args.baseline, "export.py", expectations)
    check_no_touch(args.repo, args.baseline, "ai_summary.py", expectations)
    check_pytest_and_help(args.repo, expectations)

    passed = sum(1 for e in expectations if e.passed)
    total = len(expectations)
    grading = {
        "summary": {
            "passed": passed,
            "failed": total - passed,
            "total": total,
            "pass_rate": (passed / total) if total else 0.0,
        },
        "expectations": [asdict(e) for e in expectations],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(grading, indent=2), encoding="utf-8")
    print(f"wrote {args.out} — {passed}/{total} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
