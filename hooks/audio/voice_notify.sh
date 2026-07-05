#!/usr/bin/env bash
# voice_notify.sh — 多平台多通道通知 orchestrator。
# 由 Notification / Stop hook 呼叫,讀 hook JSON from stdin。
set -uo pipefail   # 注意:不用 -e,任何失敗都不該中止(永不 crash hook)
# BASH_SOURCE 而非 $0:被 source(測試)時 $0 是 shell,會算錯路徑
AUDIO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$AUDIO_DIR/lib/config.sh"
source "$AUDIO_DIR/lib/providers.sh"

VOICE_SOURCE="${VOICE_SOURCE:-claude}"
LOG_DIR="$HOME/.claude/_logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/voice_notify_payloads.log"
log_note() { printf '%s\t%s\t%s\n' "$(date -Iseconds)" "$1" "$2" >> "$LOG" 2>/dev/null || true; }

# 對單條通道派發文字,包錯誤邊界:失敗只記 log,不影響其他通道。
dispatch_channel() {
    local ch="$1" text="$2"
    case "$ch" in
        say)      printf '%s' "$text" | bash "$AUDIO_DIR/lib/channels/say.sh" || log_note "channel_fail" "say" ;;
        tts)      printf '%s' "$text" | bash "$AUDIO_DIR/lib/channels/tts.sh" || { log_note "channel_fail" "tts"; printf '%s' "$text" | bash "$AUDIO_DIR/lib/channels/say.sh" >/dev/null 2>&1 || true; } ;;
        telegram) printf '%s' "$text" | bash "$AUDIO_DIR/lib/channels/telegram.sh" || log_note "channel_fail" "telegram" ;;
        fixed)    bash "$AUDIO_DIR/lib/channels/fixed_audio.sh" || log_note "channel_fail" "fixed" ;;
    esac
}

broadcast() {
    local text="$1" ch
    for ch in $(platform_channels); do dispatch_channel "$ch" "$text"; done
}

# --lib-only:給測試 source 用,只載入函式不跑主流程
[ "${1:-}" = "--lib-only" ] && return 0 2>/dev/null

main() {
    load_platform
    local payload; payload="$(cat)"
    [ -z "$payload" ] && payload='{"message":"Task complete","notification_type":"stop"}'
    local message ntype transcript
    message=$(echo "$payload" | jq -r '.message // .last_assistant_message // "Something happened"')
    ntype=$(echo "$payload" | jq -r '.notification_type // .hook_event_name // "unknown"')
    transcript=$(echo "$payload" | jq -r '.transcript_path // ""')

    # 抽 transcript 末段當 context(沿用現行邏輯)
    local context=""
    if [ -n "$transcript" ] && [ -f "$transcript" ]; then
        context=$(tail -30 "$transcript" | jq -r '
            if .type=="assistant" then [.message.content[]?|select(.type=="text")|.text]|join(" ")
            elif .type=="response_item" and .payload.type=="message" and .payload.role=="assistant" then [.payload.content[]?|select(.type=="output_text" or .type=="text")|.text]|join(" ")
            else empty end' 2>/dev/null | awk 'NF{last=$0} END{print last}' | cut -c1-300)
    fi
    [ -z "$context" ] && context=$(echo "$payload" | jq -r '.last_assistant_message // ""' | cut -c1-300)

    local prompt="Turn this CLI notification into a spoken alert. Include one word identifying the session context. Snarky Gen-Z, 5-8 words. No quotes, no emoji, no markdown. Do not mention 'Claude'.\nType: $ntype\nMessage: $message\nRecent: $context"

    [ "${VOICE_NOTIFY_DRY_RUN:-}" = "1" ] && exit 0

    local spoken; spoken="$(generate_text "$prompt")"
    if [ -z "$spoken" ]; then
        log_note "llm_generation_failed" "$VOICE_SOURCE"
        # 生成失敗分流:本機退隨機音檔;telegram 送原始 message
        bash "$AUDIO_DIR/lib/channels/fixed_audio.sh" >/dev/null 2>&1 || true
        printf '%s' "$message" | bash "$AUDIO_DIR/lib/channels/telegram.sh" >/dev/null 2>&1 || true
        exit 0
    fi
    log_note "spoken" "$spoken"
    broadcast "$spoken"
    exit 0
}
main
