#!/usr/bin/env python3
"""Decide whether an auto-pilot plan runs one-shot (/claude-mem:do)
or phase-by-phase (custom inner loop).

Usage:
    python3 choose_mode.py --plan path/to/plan.md

Output (stdout, single line):
    one-shot: <reason>
    phase-by-phase: <reason>
    ambiguous: <reason>

Exit code is always 0 on a successful read of the plan; the decision
itself is encoded in the first token. The orchestrator parses that.

Why a script and not model judgment: same plan must always pick the
same mode. If the model decides, two runs of the same plan can diverge,
which makes the eval suite a coin flip. Heuristic > vibes.

Tuning: the keyword sets below are the only knobs. Edit, then re-run
the eval suite; do NOT push the decision into SKILL.md prose.
"""

import argparse
import re
import sys
from pathlib import Path


# Keyword categories that push toward Mode 2 (phase-by-phase).
# Matched case-insensitively as whole words (or simple multi-word phrases).
RISK_KEYWORDS = {
    "auth": [
        "auth", "oauth", "jwt", "login", "logout", "signin", "signup",
        "password", "credential", "session", "cookie", "csrf", "2fa", "mfa",
    ],
    "secrets": ["secret", "api key", "private key"],
    "crypto": ["encryption", "decrypt", "bcrypt", "argon", "signing", "signature verify"],
    "money": [
        "payment", "billing", "invoice", "charge", "refund", "money",
        "currency", "stripe",
    ],
    "data_risk": [
        "migration", "schema change", "drop table", "deletion", "rollback",
        "backfill",
    ],
    "infra_risk": [
        "production", "deploy", "rollout", "feature flag", "breaking change",
        "breaking",
    ],
    "wide_refactor": [
        "refactor across", "rewrite", "framework upgrade", "migrate from",
    ],
}

# "token" is dual-use (JWT vs lexer/rate-limit). Only count it as risky
# if it co-occurs near another auth keyword in the same line.
DUAL_USE_TOKEN = "token"
AUTH_PROXIMITY = {
    "jwt", "auth", "session", "oauth", "bearer", "refresh", "access",
    "credential", "secret",
}

PHASE_HEADING_RE = re.compile(r"^#{1,4}\s*phase\s+(\d+)\b", re.IGNORECASE | re.MULTILINE)

# Heuristic threshold: if a phase's "What to implement" lists more than
# this many distinct file paths, it's "wide" → push toward Mode 2.
FILE_BUDGET_PER_PHASE = 5
FILE_PATH_RE = re.compile(r"`([^`\s]+\.[a-zA-Z0-9]{1,6})`")


def whole_word_search(text: str, term: str) -> bool:
    """True if `term` appears as a whole word/phrase in `text`."""
    if " " in term:
        # multi-word: simple substring is fine, since words inside a
        # phrase don't typically appear at the start/end of identifiers.
        return term in text
    pattern = r"\b" + re.escape(term) + r"\b"
    return re.search(pattern, text) is not None


def split_phases(plan_text: str) -> list[tuple[int, str]]:
    """Return [(phase_id, phase_body)] for every "## Phase N" section,
    excluding Phase 0 (doc discovery, always present in /claude-mem:make-plan
    output) and the "Verification" phase if it isn't numbered.
    """
    matches = list(PHASE_HEADING_RE.finditer(plan_text))
    phases: list[tuple[int, str]] = []
    for idx, match in enumerate(matches):
        phase_id = int(match.group(1))
        if phase_id == 0:
            continue  # doc discovery
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(plan_text)
        phases.append((phase_id, plan_text[start:end]))
    return phases


def find_risk_hits(text_lc: str) -> list[tuple[str, str]]:
    """Return [(category, keyword)] for every risk match (case-insensitive)."""
    hits: list[tuple[str, str]] = []
    for category, keywords in RISK_KEYWORDS.items():
        for kw in keywords:
            if whole_word_search(text_lc, kw):
                hits.append((category, kw))
    return hits


def token_is_auth_context(text_lc: str) -> bool:
    """Returns True only if 'token' appears AND a line containing it
    also has at least one auth-context word. False positives (lexer
    token, rate-limit token) are filtered out."""
    if not whole_word_search(text_lc, DUAL_USE_TOKEN):
        return False
    for line in text_lc.splitlines():
        if "token" not in line:
            continue
        if any(word in line for word in AUTH_PROXIMITY):
            return True
    return False


def estimate_file_count(phase_text: str) -> int:
    """Count distinct file paths mentioned in backticks. Heuristic only —
    plans don't always quote every path, so this undercounts."""
    return len(set(FILE_PATH_RE.findall(phase_text)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pick auto-pilot execution mode from a plan file")
    parser.add_argument("--plan", required=True, help="Path to the plan markdown")
    parser.add_argument("--verbose", action="store_true", help="Print all matched keywords for debugging")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.is_file():
        print(f"error: plan file not found: {plan_path}", file=sys.stderr)
        return 2

    plan_text = plan_path.read_text()
    plan_lc = plan_text.lower()
    phases = split_phases(plan_text)

    if not phases:
        # No numbered phases at all — likely a malformed plan or one tiny task.
        # Default to one-shot; the worst case is /claude-mem:do handles it.
        print("one-shot: no implementation phases detected (defaulting to do)")
        return 0

    phase_count = len(phases)
    risk_hits: list[str] = []
    wide_phases: list[int] = []

    for phase_id, body in phases:
        body_lc = body.lower()
        for category, keyword in find_risk_hits(body_lc):
            risk_hits.append(f"phase {phase_id}: {category}/{keyword!r}")
        if token_is_auth_context(body_lc):
            risk_hits.append(f"phase {phase_id}: token (auth-context)")
        files_mentioned = estimate_file_count(body)
        if files_mentioned > FILE_BUDGET_PER_PHASE:
            wide_phases.append(phase_id)

    # Caution-signal phrases that the Stage A interview captured into the plan
    # body (Stage A persists these via update_state.py history; the make-plan
    # output may also echo them in its "Context" section).
    caution_words = ("careful", "thorough", "production", "be safe", "review each step")
    cautions = [w for w in caution_words if whole_word_search(plan_lc, w)]

    if args.verbose:
        print(f"# phases: {phase_count}", file=sys.stderr)
        print(f"# risk_hits: {risk_hits}", file=sys.stderr)
        print(f"# wide_phases: {wide_phases}", file=sys.stderr)
        print(f"# cautions: {cautions}", file=sys.stderr)

    # Decision tree. Order matters: strong signals fire first.
    if phase_count > 3:
        print(f"phase-by-phase: {phase_count} phases (>3)")
        return 0

    if len(risk_hits) >= 2 or wide_phases or cautions:
        reason_bits = []
        if risk_hits:
            reason_bits.append("risk: " + "; ".join(risk_hits[:3]))
        if wide_phases:
            reason_bits.append(f"wide phases: {wide_phases}")
        if cautions:
            reason_bits.append(f"caution words: {cautions}")
        print(f"phase-by-phase: {' | '.join(reason_bits)}")
        return 0

    if len(risk_hits) == 1 and phase_count == 3:
        # Exactly the gray zone described in stage-b-branch.md.
        print(f"ambiguous: {phase_count} phases with one mild risk hit ({risk_hits[0]})")
        return 0

    if len(risk_hits) == 1:
        # One risk match in a 1- or 2-phase plan — still risky enough.
        print(f"phase-by-phase: single risk hit ({risk_hits[0]}) outweighs small plan")
        return 0

    # All clear: small plan, no risk keywords, narrow file scope.
    print(f"one-shot: {phase_count} phases, no risk keywords, narrow file scope")
    return 0


if __name__ == "__main__":
    sys.exit(main())
