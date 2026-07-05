#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
export VOICE_SAY_DRYRUN=1

out=$(echo "hi there" | VOICE_PLATFORM=mac bash "$DIR/../channels/say.sh")
assert_contains "$out" "say" "mac→say"
out=$(echo "hi there" | VOICE_PLATFORM=wsl bash "$DIR/../channels/say.sh")
assert_contains "$out" "System.Speech" "wsl→System.Speech"
rc=$(echo "hi" | VOICE_PLATFORM=linux bash "$DIR/../channels/say.sh"; echo $?)
assert_eq "$rc" "1" "linux→略過(回1)"
test_summary
