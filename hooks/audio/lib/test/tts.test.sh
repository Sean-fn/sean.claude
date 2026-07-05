#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
export VOICE_TTS_DRYRUN=1 VOICE_CONFIG_FILE="$DIR/../../notify.config.json"

out=$(echo "hello" | bash "$DIR/../channels/tts.sh")
assert_contains "$out" "lab-r2" "用 config 的 ssh_host"
assert_contains "$out" "speaker=Aiden" "帶 speaker 參數"
rc=$(printf '' | bash "$DIR/../channels/tts.sh"; echo $?)
assert_eq "$rc" "1" "空文字回1"
test_summary
