#!/usr/bin/env bash
# config.sh — 平台偵測 + 設定讀取。設計為可 source。
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_DIR="$(cd "$LIB_DIR/.." && pwd)"
VOICE_CONFIG_FILE="${VOICE_CONFIG_FILE:-$AUDIO_DIR/notify.config.json}"

detect_platform() {
    [ -n "${VOICE_PLATFORM_OVERRIDE:-}" ] && { printf '%s' "$VOICE_PLATFORM_OVERRIDE"; return; }
    local uname_s="${VOICE_UNAME_OVERRIDE:-$(uname -s)}"
    local procfile="${VOICE_PROC_VERSION:-/proc/version}"
    case "$uname_s" in
        Darwin) echo mac ;;
        Linux)
            if [ -n "${WSL_DISTRO_NAME:-}" ]; then echo wsl
            elif grep -qi microsoft "$procfile" 2>/dev/null; then echo wsl
            else echo linux; fi ;;
        MINGW*|MSYS*|CYGWIN*) echo windows ;;
        *) echo linux ;;
    esac
}
