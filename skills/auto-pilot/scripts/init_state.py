#!/usr/bin/env python3
"""Create the initial state.json for an auto-pilot task.

Usage:
    python3 init_state.py --slug my-task --goal "Add JWT auth so that ..."

Writes to: .claude/state/auto-pilot/<slug>/state.json (relative to CWD).

Exits non-zero if the state file already exists — auto-pilot is supposed
to call this exactly once per task. Re-running it would clobber history,
so the orchestrator gets a clear error instead of silent data loss.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


STATE_ROOT = Path(".claude/state/auto-pilot")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize auto-pilot state.json")
    parser.add_argument("--slug", required=True, help="Task slug (used as directory name)")
    parser.add_argument("--goal", required=True, help="Stage A goal sentence")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing state.json (rarely correct; the orchestrator should not pass this)",
    )
    args = parser.parse_args()

    slug = args.slug.strip()
    if not slug or "/" in slug or slug.startswith("."):
        print(f"error: invalid slug {args.slug!r}", file=sys.stderr)
        return 2

    state_dir = STATE_ROOT / slug
    state_path = state_dir / "state.json"

    if state_path.exists() and not args.force:
        print(f"error: {state_path} already exists; pass --force to overwrite", file=sys.stderr)
        return 1

    state_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "task_slug": slug,
        "stage": "A",
        "execution_mode": "undecided",
        "goal": args.goal,
        "plan_path": None,
        "phases": [],
        "current_phase": None,
        "stop_reason": None,
        "history": [
            {"timestamp": now_iso(), "event": "task_initialized", "goal": args.goal}
        ],
    }

    # Write atomically: write to a temp file, then rename. Avoids a partial
    # state.json if the process gets killed mid-write.
    tmp_path = state_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(tmp_path, state_path)

    print(str(state_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
