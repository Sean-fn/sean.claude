#!/usr/bin/env python3
"""Decide which review commands to run for a single phase of an auto-pilot plan.

Usage:
    python3 classify_phase.py --plan path/to/plan.md --phase 2

Output (stdout): a JSON list of review command names.
    ["self-review"]
    ["self-review", "security-review"]
    ["self-review", "security-review", "optimize"]
    ["self-review", "file-by-file-review"]

`/self-review` is ALWAYS first; the orchestrator runs them in order.

Keyword sets are intentionally simple — substring/whole-word matching on the
phase body. We tolerate false positives (running /security-review when not
strictly needed costs a few seconds; skipping it when needed is dangerous).
"""

import argparse
import json
import re
import sys
from pathlib import Path


SECURITY_KEYWORDS = [
    # auth
    "auth", "oauth", "jwt", "login", "logout", "signin", "signup",
    "password", "credential", "session", "cookie", "csrf", "2fa", "mfa",
    # secrets / crypto
    "secret", "api key", "private key", "encryption", "decrypt", "bcrypt",
    "argon", "signing", "signature verify",
    # input / sql
    "user input", "request body", "query string", "form data", "file upload",
    "multipart", "raw query", "db.execute", "where clause",
    # permissions / network
    "authorize", "permission", "rbac", "acl", "cors", "csp", "xss",
    "injection", "sanitize", "escape",
]

# Dual-use, only counts when adjacent to auth context (prevents lexer/parser
# tokens from triggering /security-review).
DUAL_USE_TOKEN = "token"
AUTH_PROXIMITY = {
    "jwt", "auth", "session", "oauth", "bearer", "refresh", "access",
    "credential", "secret",
}

OPTIMIZE_KEYWORDS = [
    # db
    "n+1", "eager load", "index", "migration", "bulk insert", "batch",
    # algorithm
    "nested loop", "o(n^2)", "complexity", "recursion", "memoize",
    # i/o
    "await in loop", "parallel", "concurrent", "stream", "pagination",
    "lazy load",
    # frontend
    "re-render", "memo", "usememo", "usecallback", "bundle size",
    "code split",
    # memory
    "leak", "weakmap", "large array", "large object",
]
# These are too generic to match alone (they appear in non-perf contexts
# constantly), so they only count if at least one OPTIMIZE_KEYWORDS hit
# also fires.
OPTIMIZE_GENERIC_BOOSTERS = ["loop", "query", "cache"]

PHASE_HEADING_RE = re.compile(r"^#{1,4}\s*phase\s+(\d+)\b", re.IGNORECASE | re.MULTILINE)
FILE_PATH_RE = re.compile(r"`([^`\s]+\.[a-zA-Z0-9]{1,6})`")
LARGE_DIFF_THRESHOLD = 10


def whole_word_search(text: str, term: str) -> bool:
    if " " in term or any(c in term for c in "+()."):
        return term in text  # multi-word or punctuated: literal substring
    return re.search(r"\b" + re.escape(term) + r"\b", text) is not None


def extract_phase_body(plan_text: str, phase_number: int) -> str:
    matches = list(PHASE_HEADING_RE.finditer(plan_text))
    for idx, match in enumerate(matches):
        if int(match.group(1)) == phase_number:
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(plan_text)
            return plan_text[start:end]
    raise ValueError(f"phase {phase_number} not found in plan")


def needs_security_review(text_lc: str) -> bool:
    for kw in SECURITY_KEYWORDS:
        if whole_word_search(text_lc, kw):
            return True
    # token only counts in auth context
    if whole_word_search(text_lc, DUAL_USE_TOKEN):
        for line in text_lc.splitlines():
            if "token" in line and any(w in line for w in AUTH_PROXIMITY):
                return True
    return False


def needs_optimize(text_lc: str) -> bool:
    strong_hit = any(whole_word_search(text_lc, kw) for kw in OPTIMIZE_KEYWORDS)
    if strong_hit:
        return True
    # Generic words alone don't fire; they need to co-occur with another
    # generic booster to count. Keeps "implement a query helper" from
    # triggering /optimize.
    booster_hits = sum(1 for kw in OPTIMIZE_GENERIC_BOOSTERS if whole_word_search(text_lc, kw))
    return booster_hits >= 2


def needs_file_by_file(phase_text: str) -> bool:
    distinct_files = len(set(FILE_PATH_RE.findall(phase_text)))
    return distinct_files > LARGE_DIFF_THRESHOLD


def main() -> int:
    parser = argparse.ArgumentParser(description="Pick review commands for an auto-pilot phase")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--phase", type=int, required=True)
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.is_file():
        print(f"error: plan file not found: {plan_path}", file=sys.stderr)
        return 2

    plan_text = plan_path.read_text()
    try:
        body = extract_phase_body(plan_text, args.phase)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    body_lc = body.lower()
    reviews = ["self-review"]

    if needs_security_review(body_lc):
        reviews.append("security-review")
    if needs_optimize(body_lc):
        reviews.append("optimize")
    if needs_file_by_file(body):
        reviews.append("file-by-file-review")

    print(json.dumps(reviews))
    return 0


if __name__ == "__main__":
    sys.exit(main())
