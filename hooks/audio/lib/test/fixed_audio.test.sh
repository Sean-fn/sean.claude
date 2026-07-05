#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
export VOICE_PLAYER_DRYRUN=1 VOICE_PLATFORM=linux
source "$DIR/../channels/fixed_audio.sh"

out=$(play_random)
assert_contains "$out" ".mp3" "隨機挑到 mp3 並交給 player"
test_summary
