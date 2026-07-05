#!/usr/bin/env bash
# fixed_audio.sh — 播隨機音檔(fallback)。可 source。
CH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CH_DIR/../config.sh"
source "$CH_DIR/../player.sh"

play_random() {
    local clips=("$AUDIO_DIR/_voices/user_action/"*.mp3)
    [ -f "${clips[0]}" ] || return 1
    play_audio "${clips[RANDOM % ${#clips[@]}]}"
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then play_random; fi
