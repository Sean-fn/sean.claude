#!/usr/bin/env python3
"""
Claude Code usage statusline script.
Fetches real-time usage from Anthropic's OAuth usage API with caching.
Output: 5h: 43%/59% · 7d: 35%/42%
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


def drain_stdin():
    """Claude Code pipes session JSON to stdin — drain it without blocking."""
    if not sys.stdin.isatty():
        try:
            sys.stdin.read()
        except Exception:
            pass


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


def format_bar(actual, expected):
    """Return colored 'actual%/expected%' string using ANSI if supported."""
    use_color = sys.stdout.isatty() or os.environ.get("COLORTERM") or os.environ.get("TERM", "").startswith("xterm")
    actual_int = round(actual)
    expected_int = round(expected)

    if use_color:
        if actual <= expected:
            # Under pace — green
            color = "\033[32m"
        elif actual <= expected + 10:
            # Slightly over — yellow
            color = "\033[33m"
        else:
            # Well over — red
            color = "\033[31m"
        reset = "\033[0m"
        return f"{color}{actual_int}%{reset}/{expected_int}%"
    else:
        return f"{actual_int}%/{expected_int}%"


def main():
    drain_stdin()

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
                stale_suffix = " (cached)"
            else:
                print(f"API err {e.code}", end="")
                sys.exit(0)
        except Exception as e:
            if cached_data is not None:
                data = cached_data
                stale_suffix = " (cached)"
            else:
                print("usage: err", end="")
                sys.exit(0)

    try:
        five = data["five_hour"]
        seven = data["seven_day"]

        exp_5h = expected_pct(five["resets_at"], FIVE_HOURS)
        exp_7d = expected_pct(seven["resets_at"], SEVEN_DAYS)

        bar_5h = format_bar(five["utilization"], exp_5h)
        bar_7d = format_bar(seven["utilization"], exp_7d)

        print(f"5h: {bar_5h} · 7d: {bar_7d}{stale_suffix}", end="")
    except (KeyError, TypeError):
        print("usage: parse err", end="")


if __name__ == "__main__":
    main()
