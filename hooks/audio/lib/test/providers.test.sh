#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
export VOICE_CONFIG_FILE="$DIR/fixtures/echo.config.json"
source "$DIR/../config.sh"
source "$DIR/../providers.sh"

assert_eq "$(generate_text 'hello world')" "GOT: hello world" "{PROMPT} 代換 + 執行"
assert_eq "$(VOICE_PROVIDER=missing generate_text 'x'; echo $?)" "1" "缺 provider 回1"
test_summary
