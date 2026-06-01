#!/usr/bin/env python3
"""Atomic mutations on an auto-pilot state.json.

Usage examples:
    python3 update_state.py --slug my-task --set stage=B --set plan_path=plans/foo.md
    python3 update_state.py --slug my-task --mark-phase-done 2 --set current_phase=3
    python3 update_state.py --slug my-task --set stop_reason="3: do failed"
    python3 update_state.py --slug my-task --add-phase '{"id":1,"title":"Build X"}'
    python3 update_state.py --slug my-task --log-event '{"event":"review_run","phase":1}'

Why this script exists: the orchestrator (the model running auto-pilot)
should NOT be writing JSON by hand. Hand-written JSON drifts — keys get
typo'd, history gets accidentally clobbered, atomicity is lost. This
gives every state mutation a single, deterministic entry point.

Every mutation appends a "history" entry, even simple --set calls, so the
state file doubles as an event log.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


STATE_ROOT = Path(".claude/state/auto-pilot")
ALLOWED_TOP_LEVEL_KEYS = {
    "stage",
    "execution_mode",
    "goal",
    "plan_path",
    "current_phase",
    "stop_reason",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_set(raw: str) -> tuple[str, object]:
    """Parse a --set k=v pair. Coerces obvious types (int, null)."""
    if "=" not in raw:
        raise ValueError(f"--set expects key=value, got {raw!r}")
    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if key not in ALLOWED_TOP_LEVEL_KEYS:
        raise ValueError(
            f"key {key!r} is not a writable top-level field. "
            f"Allowed: {sorted(ALLOWED_TOP_LEVEL_KEYS)}"
        )
    coerced: object
    if value == "null":
        coerced = None
    elif value.isdigit():
        coerced = int(value)
    else:
        coerced = value
    return key, coerced


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        print(f"error: {state_path} does not exist; run init_state.py first", file=sys.stderr)
        sys.exit(1)
    return json.loads(state_path.read_text())


def save_state(state_path: Path, state: dict) -> None:
    tmp_path = state_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2) + "\n")
    os.replace(tmp_path, state_path)


def mark_phase_done(state: dict, phase_id: int) -> None:
    for phase in state.get("phases", []):
        if phase.get("id") == phase_id:
            phase["status"] = "done"
            return
    raise ValueError(f"no phase with id={phase_id} in state.phases")


def add_phase(state: dict, phase_json: str) -> None:
    phase = json.loads(phase_json)
    if "id" not in phase or "title" not in phase:
        raise ValueError("phase JSON must include 'id' and 'title'")
    phase.setdefault("status", "pending")
    phase.setdefault("review_iterations", 0)
    phase.setdefault("last_review_summary", None)
    state.setdefault("phases", []).append(phase)


def log_event(state: dict, event_json: str) -> None:
    """Append a structured event to history. Always stamps the timestamp."""
    event = json.loads(event_json)
    event["timestamp"] = now_iso()
    state.setdefault("history", []).append(event)


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomically mutate auto-pilot state.json")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--set", action="append", default=[], dest="set_pairs",
                        help="key=value (repeatable). Allowed keys: " + ", ".join(sorted(ALLOWED_TOP_LEVEL_KEYS)))
    parser.add_argument("--mark-phase-done", type=int, default=None, metavar="N")
    parser.add_argument("--add-phase", default=None, metavar="JSON",
                        help='Append a phase, e.g. \'{"id":1,"title":"Build X"}\'')
    parser.add_argument("--log-event", default=None, metavar="JSON",
                        help='Append a structured event, e.g. \'{"event":"phase_started","phase":1}\'')
    parser.add_argument("--increment-iteration", type=int, default=None, metavar="N",
                        help="Bump review_iterations on phase N by 1")
    args = parser.parse_args()

    state_path = STATE_ROOT / args.slug / "state.json"
    state = load_state(state_path)

    changes: list[dict] = []

    for raw in args.set_pairs:
        try:
            key, value = parse_set(raw)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        state[key] = value
        changes.append({"set": key, "value": value})

    if args.mark_phase_done is not None:
        try:
            mark_phase_done(state, args.mark_phase_done)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        changes.append({"phase_done": args.mark_phase_done})

    if args.add_phase is not None:
        try:
            add_phase(state, args.add_phase)
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"error: --add-phase: {exc}", file=sys.stderr)
            return 2
        changes.append({"phase_added": args.add_phase})

    if args.increment_iteration is not None:
        target = args.increment_iteration
        bumped = False
        for phase in state.get("phases", []):
            if phase.get("id") == target:
                phase["review_iterations"] = phase.get("review_iterations", 0) + 1
                changes.append({"iteration_bumped": target, "now": phase["review_iterations"]})
                bumped = True
                break
        if not bumped:
            print(f"error: no phase with id={target}", file=sys.stderr)
            return 2

    if args.log_event is not None:
        try:
            log_event(state, args.log_event)
        except json.JSONDecodeError as exc:
            print(f"error: --log-event JSON parse: {exc}", file=sys.stderr)
            return 2
        # already appended to history; don't double-log

    if not changes and args.log_event is None:
        print("error: nothing to do; pass --set, --mark-phase-done, --add-phase, --increment-iteration, or --log-event",
              file=sys.stderr)
        return 2

    if changes:
        state.setdefault("history", []).append({
            "timestamp": now_iso(),
            "event": "state_updated",
            "changes": changes,
        })

    save_state(state_path, state)
    print(str(state_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
