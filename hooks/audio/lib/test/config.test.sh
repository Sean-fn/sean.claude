#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/assert.sh"
source "$DIR/../config.sh"

assert_eq "$(VOICE_UNAME_OVERRIDE=Darwin detect_platform)" "mac" "Darwin→mac"
assert_eq "$(VOICE_UNAME_OVERRIDE=Linux WSL_DISTRO_NAME=Ubuntu detect_platform)" "wsl" "env-var 快路→wsl"

# env-var 空掉時,/proc/version 兜底
fake=$(mktemp); echo "Linux ... microsoft-standard-WSL2 ..." > "$fake"
assert_eq "$(VOICE_UNAME_OVERRIDE=Linux WSL_DISTRO_NAME= VOICE_PROC_VERSION=$fake detect_platform)" "wsl" "procfile 兜底→wsl"
plain=$(mktemp); echo "Linux ... generic ..." > "$plain"
assert_eq "$(VOICE_UNAME_OVERRIDE=Linux WSL_DISTRO_NAME= VOICE_PROC_VERSION=$plain detect_platform)" "linux" "純linux"
rm -f "$fake" "$plain"

assert_eq "$(VOICE_UNAME_OVERRIDE=MINGW64_NT detect_platform)" "windows" "MINGW→windows"
assert_eq "$(VOICE_PLATFORM_OVERRIDE=mac VOICE_UNAME_OVERRIDE=Linux detect_platform)" "mac" "override 短路"
assert_eq "$(VOICE_PLATFORM_OVERRIDE=wsl bash "$DIR/../config.sh" --print-platform)" "wsl" "CLI --print-platform block"

export VOICE_CONFIG_FILE="$DIR/../../notify.config.json"
assert_eq "$(cfg '.provider' fallback)" "copilot" "cfg 讀 provider"
assert_eq "$(cfg '.telegram.idle_threshold_sec' 999)" "180" "cfg 讀巢狀"
assert_eq "$(cfg '.nonexistent' DEF)" "DEF" "cfg 缺值回 default"
assert_eq "$(VOICE_PLATFORM=wsl platform_channels)" "say telegram" "wsl 通道清單"
assert_eq "$(VOICE_PLATFORM=linux platform_channels)" "tts telegram" "linux 通道清單"
assert_eq "$(VOICE_PLATFORM=wsl VOICE_CHANNELS=telegram platform_channels)" "telegram" "env 覆蓋通道"
test_summary
