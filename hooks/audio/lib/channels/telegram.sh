#!/usr/bin/env bash
# telegram.sh — 閒置感知 Bot API 推播。吃 stdin。dual source/CLI。
CH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CH_DIR/../config.sh"
ENV_FILE="${VOICE_TG_ENV:-$AUDIO_DIR/channels/telegram/notify.env}"

query_idle_sec() {
    [ -n "${VOICE_IDLE_OVERRIDE:-}" ] && { [ "$VOICE_IDLE_OVERRIDE" = "fail" ] && return 1; printf '%s' "$VOICE_IDLE_OVERRIDE"; return; }
    local idle
    idle=$(powershell.exe -NoProfile -Command "Add-Type 'using System;using System.Runtime.InteropServices;public class I{[DllImport(\"user32.dll\")]public static extern bool GetLastInputInfo(ref L p);[StructLayout(LayoutKind.Sequential)]public struct L{public uint s;public uint t;}}'; \$l=New-Object I+L; \$l.s=[Runtime.InteropServices.Marshal]::SizeOf(\$l); [void][I]::GetLastInputInfo([ref]\$l); [int](([Environment]::TickCount-\$l.t)/1000)" 2>/dev/null | tr -d '\r')
    [ -n "$idle" ] || return 1
    printf '%s' "$idle"
}

should_push() {
    local threshold; threshold="${VOICE_THRESHOLD_OVERRIDE:-$(cfg '.telegram.idle_threshold_sec' 180)}"
    [ "$threshold" -lt 0 ] && { echo push; return; }   # -1 哨兵 = 永遠推
    local idle; idle="$(query_idle_sec)" || {
        [ "$(cfg '.telegram.idle_query_fail_mode' push)" = "push" ] && echo push || echo skip; return; }
    [ "$idle" -lt "$threshold" ] && echo skip || echo push
}

tg_send() {
    [ -n "${VOICE_TG_DRYRUN:-}" ] && { echo "tg_send: $1"; return; }
    [ -f "$ENV_FILE" ] || return 1
    source "$ENV_FILE"
    [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ] || return 1
    curl -sf "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
         --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
         --data-urlencode "text=$1" --max-time 10 >/dev/null 2>&1
}

telegram_notify() {
    local text; text="$(cat)"; [ -z "$text" ] && return 1
    [ "$(should_push)" = "push" ] || return 0   # 人在,靜音,非錯誤
    tg_send "$text"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    [ "$1" = "--print-idle" ] && { query_idle_sec; echo; exit 0; }
    telegram_notify
fi
