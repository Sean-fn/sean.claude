#!/usr/bin/env bash
# tts.sh — 文字→tts_server 產 mp3→player。吃 stdin。dual source/CLI。
CH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CH_DIR/../config.sh"
source "$CH_DIR/../player.sh"

tts_speak() {
    local text; text="$(cat)"; [ -z "$text" ] && return 1
    local host speaker instruct
    host="$(cfg '.tts.ssh_host' lab-r2)"
    speaker="$(cfg '.tts.speaker' Aiden)"
    instruct="$(cfg '.tts.instruct' 'speak clearly')"
    local out="$AUDIO_DIR/_voices/generated/tts_$$.mp3"; mkdir -p "$(dirname "$out")"

    if [ -n "${VOICE_TTS_DRYRUN:-}" ]; then
        echo "ssh $host curl speak_stream speaker=$speaker instruct=$instruct"; return
    fi
    # 經 ssh ProxyJump 打自架 tts server;stdin 傳文字避開引號地獄
    if printf '%s' "$text" | ssh -o ConnectTimeout=5 -o BatchMode=yes "$host" \
         "curl -sf -G 'http://localhost:7865/speak_stream' --data-urlencode text@- --data-urlencode 'speaker=${speaker}' --data-urlencode 'instruct=${instruct}' --max-time 30" \
         > "$out" 2>/dev/null && [ -s "$out" ]; then
        play_audio "$out"
    else
        rm -f "$out"; return 1
    fi
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then tts_speak; fi
