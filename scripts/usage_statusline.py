#!/usr/bin/env python3
"""
Claude Code usage statusline script.
Fetches real-time usage from Anthropic's OAuth usage API with caching.
Output: [█░░░░░░░░░]17% · 5h □□□□□ 17% · 7d ■■□□□ 43%/59% · 💬 38 · $0.48
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CACHE_FILE = "/tmp/claude_usage_cache.json"
CACHE_TTL = 300  # 5 minutes
API_URL = "https://api.anthropic.com/api/oauth/usage"
FIVE_HOURS = 5 * 3600
SEVEN_DAYS = 7 * 86400

CONTEXT_LIMITS = {
    "claude-opus":   200_000,
    "claude-sonnet": 200_000,
    "claude-haiku":  200_000,
}


def parse_stdin():
    """Parse Claude Code's session JSON from stdin."""
    if sys.stdin.isatty():
        return {}
    try:
        return json.loads(sys.stdin.read())
    except Exception:
        return {}


def get_context_limit(model_id):
    for prefix, limit in CONTEXT_LIMITS.items():
        if prefix in model_id:
            return limit
    return 200_000  # safe default


def read_transcript(path):
    """Returns (msg_count, last_input_tokens) from JSONL session file."""
    msg_count = 0
    last_input_tokens = 0
    if not path:
        return msg_count, last_input_tokens
    try:
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("type") == "assistant":
                    msg_count += 1
                    usage = entry.get("message", {}).get("usage", {})
                    t = (usage.get("input_tokens", 0)
                         + usage.get("cache_creation_input_tokens", 0)
                         + usage.get("cache_read_input_tokens", 0))
                    if t:
                        last_input_tokens = t
    except Exception:
        pass
    return msg_count, last_input_tokens


def make_ctx_bar(pct, width=10):
    """[█░░░░░░░░░] style bar, colored by threshold."""
    filled = min(width, round(pct / 100 * width))
    bar = "[" + "█" * filled + "░" * (width - filled) + "]"
    if pct >= 90:
        return f"\033[31m{bar}\033[0m"   # red
    elif pct >= 70:
        return f"\033[33m{bar}\033[0m"   # yellow
    return f"\033[32m{bar}\033[0m"        # green


def make_blocks(pct, width=5, fill="■", empty="□"):
    """■■□□□ style block bar."""
    filled = min(width, round(pct / 100 * width))
    return fill * filled + empty * (width - filled)


def fmt_tokens(n):
    """Format token count: 45200 -> '45.2k tok', 1200 -> '1.2k tok', 800 -> '800 tok'"""
    if n >= 100_000:
        return f"{n // 1000}k tok"
    elif n >= 1_000:
        return f"{n / 1000:.1f}k tok"
    return f"{n} tok"


def load_cache():
    """Return (data, age_seconds) or (None, None) if cache missing/invalid."""
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        age = time.time() - cache.get("timestamp", 0)
        return cache.get("data"), age
    except Exception:
        return None, None


def save_cache(data):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump({"timestamp": time.time(), "data": data}, f)
    except Exception:
        pass


def get_token():
    """Retrieve OAuth access token from macOS Keychain."""
    result = subprocess.run(
        ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("keychain lookup failed")
    creds = json.loads(result.stdout.strip())
    return creds["claudeAiOauth"]["accessToken"]


def fetch_usage(token):
    """Call the usage API. Returns parsed JSON dict."""
    req = Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-code/2.0.32",
        },
    )
    with urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def expected_pct(resets_at_str, window_seconds):
    """Calculate expected usage % based on time elapsed in the window."""
    resets_at = datetime.fromisoformat(resets_at_str)
    now = datetime.now(timezone.utc)
    time_remaining = (resets_at - now).total_seconds()
    elapsed = window_seconds - time_remaining
    pct = (elapsed / window_seconds) * 100
    return max(0.0, min(100.0, pct))


def main():
    session = parse_stdin()
    cost_usd   = session.get("cost", {}).get("total_cost_usd")
    model_id   = session.get("model", {}).get("id", "")
    transcript = session.get("transcript_path", "")

    # --- Transcript data ---
    msg_count, last_tokens = read_transcript(transcript)
    ctx_limit = get_context_limit(model_id)
    ctx_pct = (last_tokens / ctx_limit * 100) if last_tokens else None

    # --- API usage (cached) ---
    cached_data, cache_age = load_cache()
    stale_suffix = ""
    data = None

    if cached_data is not None and cache_age < CACHE_TTL:
        data = cached_data
    else:
        try:
            token = get_token()
            data = fetch_usage(token)
            save_cache(data)
        except HTTPError as e:
            if e.code == 429 and cached_data is not None:
                data = cached_data
                stale_suffix = "~"
            else:
                print("usage: err", end="")
                sys.exit(0)
        except Exception:
            if cached_data is not None:
                data = cached_data
                stale_suffix = "~"
            else:
                print("usage: err", end="")
                sys.exit(0)

    try:
        five  = data["five_hour"]
        seven = data["seven_day"]
        exp_5h = expected_pct(five["resets_at"], FIVE_HOURS)
        exp_7d = expected_pct(seven["resets_at"], SEVEN_DAYS)
    except (KeyError, TypeError):
        print("usage: parse err", end="")
        return

    # --- Build parts ---
    line1 = []
    line2 = []
    line3 = []
    r = "\033[0m"

    # Line 1: context bar · message count
    if ctx_pct is not None:
        bar = make_ctx_bar(ctx_pct)
        line1.append(f"{bar}{round(ctx_pct)}%")
    if msg_count:
        line1.append(f"💬 {msg_count}")

    # Line 2: 5h · cost
    blocks_5h  = make_blocks(five["utilization"])
    actual_5h  = round(five["utilization"])
    exp_5h_int = round(exp_5h)
    if actual_5h <= exp_5h:
        c5 = "\033[32m"
    elif actual_5h <= exp_5h + 10:
        c5 = "\033[33m"
    else:
        c5 = "\033[31m"
    line2.append(f"5h {blocks_5h} {c5}{actual_5h}%{r}/{exp_5h_int}%")
    if cost_usd is not None:
        line2.append(f"${cost_usd:.2f}")

    # Line 3: 7d · tok
    blocks_7d  = make_blocks(seven["utilization"])
    actual_7d  = round(seven["utilization"])
    exp_7d_int = round(exp_7d)
    if actual_7d <= exp_7d:
        c7 = "\033[32m"
    elif actual_7d <= exp_7d + 10:
        c7 = "\033[33m"
    else:
        c7 = "\033[31m"
    line3.append(f"7d {blocks_7d} {c7}{actual_7d}%{r}/{exp_7d_int}%")
    if last_tokens:
        line3.append(fmt_tokens(last_tokens))

    lines = [" · ".join(line1), " · ".join(line2), " · ".join(line3)]
    print("\n".join(lines) + stale_suffix, end="")


if __name__ == "__main__":
    main()
