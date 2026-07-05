#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
export VOICE_CONFIG_FILE="$DIR/../../notify.config.json"
# dry-run 全通道
export VOICE_SAY_DRYRUN=1 VOICE_TTS_DRYRUN=1 VOICE_TG_DRYRUN=1 VOICE_PLAYER_DRYRUN=1
export VOICE_IDLE_OVERRIDE=999   # 強制 telegram 推
source "$DIR/../../voice_notify.sh" --lib-only

out=$(VOICE_PLATFORM=wsl broadcast "hello there")
assert_contains "$out" "System.Speech" "wsl 廣播含 say"
assert_contains "$out" "tg_send" "wsl 廣播含 telegram"
test_summary
