#!/usr/bin/env bash
# providers.sh — 讀 provider cmd 陣列,代換 {PROMPT},執行。可 source。
generate_text() {
    local prompt="$1"
    local provider="${VOICE_PROVIDER:-$(cfg '.provider' copilot)}"
    local cmd=() line
    while IFS= read -r line; do cmd+=("$line"); done \
        < <(jq -r ".providers.\"$provider\".cmd[]?" "$VOICE_CONFIG_FILE" 2>/dev/null)
    [ "${#cmd[@]}" -eq 0 ] && return 1
    local i; for i in "${!cmd[@]}"; do cmd[$i]="${cmd[$i]//\{PROMPT\}/$prompt}"; done
    "${cmd[@]}" 2>/dev/null
}
