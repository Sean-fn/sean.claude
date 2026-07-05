#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
export VOICE_CONFIG_FILE="$DIR/../../notify.config.json"
source "$DIR/../config.sh"
source "$DIR/../channels/telegram.sh"

assert_eq "$(VOICE_IDLE_OVERRIDE=10 should_push)" "skip" "idle<門檻→skip(人在)"
assert_eq "$(VOICE_IDLE_OVERRIDE=300 should_push)" "push" "idle>門檻→push(離開)"
assert_eq "$(VOICE_IDLE_OVERRIDE=fail should_push)" "push" "查詢失敗→照推(預設)"
assert_eq "$(VOICE_THRESHOLD_OVERRIDE=-1 VOICE_IDLE_OVERRIDE=10 should_push)" "push" "門檻-1→永遠推"
test_summary
