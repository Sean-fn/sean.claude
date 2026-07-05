#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
source "$DIR/../player.sh"
export VOICE_PLAYER_DRYRUN=1
f=$(mktemp --suffix=.mp3)

assert_contains "$(VOICE_PLATFORM=mac play_audio "$f")" "afplay" "mac→afplay"
assert_contains "$(VOICE_PLATFORM=linux play_audio "$f")" "ffplay" "linux→ffplay"
assert_eq "$(play_audio /no/such/file.mp3; echo $?)" "1" "缺檔回1"
rm -f "$f"
test_summary
