#!/usr/bin/env bash
# voice_notify.sh — Generate a contextual TTS notification to get the user's attention.
# Called by the Notification and Stop hooks. Reads hook JSON from stdin.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VOICE_DIR_BASE="$SCRIPT_DIR/_voices"

# Detect whether audio should play locally or on the target machine
TARGET_IP="100.93.183.121"
TARGET_SSH="sean@${TARGET_IP}"

if ifconfig 2>/dev/null | grep -q "inet ${TARGET_IP}"; then
    IS_REMOTE=false
else
    IS_REMOTE=true
fi

# play_audio: plays a local file either locally or on the target machine via SSH
play_audio() {
    local file="$1"
    if [ "$IS_REMOTE" = true ]; then
        local remote_file="/tmp/$(basename "$file")"
        scp -q "$file" "${TARGET_SSH}:${remote_file}"
        ssh "${TARGET_SSH}" "afplay -v '${CLAUDE_TTS_VOLUME:-1.7}' '${remote_file}'"
    else
        afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "$file"
    fi
}

# Mic check: if recording, play a subtle pop and bail — don't interrupt the call
if "$SCRIPT_DIR/mic_status" 2>/dev/null; then
    play_audio "$VOICE_DIR_BASE/sound_during_mic/mixkit-long-pop-2358.wav"
    exit 0
fi

play_random() {
    if [ "$IS_REMOTE" = true ]; then
        ssh "${TARGET_SSH}" "
            clips=(\"/Users/sean/.claude/hooks/audio/_voices/user_action/\"*.mp3)
            afplay -v '${CLAUDE_TTS_VOLUME:-1.7}' \"\${clips[RANDOM % \${#clips[@]}]}\"
        "
    else
        local clips=("$VOICE_DIR_BASE/user_action/"*.mp3)
        afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "${clips[RANDOM % ${#clips[@]}]}"
    fi
}

# Toggle: "generated" = Gemini + TTS on the fly, "random" = pick from pre-recorded clips
MODE="${CLAUDE_VOICE_MODE:-generated}"

if [ "$MODE" = "random" ]; then
    play_random
    exit 0
fi

GENERATED_DIR="$VOICE_DIR_BASE/generated"
mkdir -p "$GENERATED_DIR"

LOG_DIR="$HOME/.claude/_logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/voice_notify_payloads.log"

# Read hook payload (may be empty for Stop hook)
PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
    PAYLOAD='{"message":"Task complete","notification_type":"stop"}'
fi

MESSAGE=$(echo "$PAYLOAD" | jq -r '.message // "Something happened"')
NOTIFICATION_TYPE=$(echo "$PAYLOAD" | jq -r '.notification_type // "unknown"')
TRANSCRIPT=$(echo "$PAYLOAD" | jq -r '.transcript_path // ""')

# Extract last assistant message from transcript (JSONL format)
CONTEXT=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    CONTEXT=$(tail -30 "$TRANSCRIPT" \
        | jq -r 'select(.type == "assistant") | [.message.content[] | select(.type == "text") | .text] | join(" ")' 2>/dev/null \
        | tail -1 \
        | cut -c1-300)
fi

PROMPT="Turn this CLI notification into a spoken alert. around 5-8 words. Snarky. No quotes, no emoji, no markdown. Just the sentence. Reference what the user is actually working on. You can use GEN-Z language or qurky formal tone wiht different emotion if suitable. DO NOT MENTION THE WORD 'Claude' IN THE RESPONSE

Type: $NOTIFICATION_TYPE
Message: $MESSAGE
Recent conversation: $CONTEXT"

# Generate spoken text via Gemini; fall back to random clip if it fails
if ! SPOKEN=$(echo "" | ollama run glm-5.1:cloud --think=false "$PROMPT" 2>/dev/null) || [ -z "$SPOKEN" ]; then
    echo "LLM generation failed or returned empty\n"STDERR/STDOUT: $SPOKEN"" >> "$LOG"
    play_random
    exit 0
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SAFE_NAME=$(echo "$SPOKEN" | tr -cd '[:alnum:] ' | tr ' ' '_' | cut -c1-60)
OUTFILE="$GENERATED_DIR/${TIMESTAMP}_${SAFE_NAME}.mp3"

# Call remote TTS (returns binary MP3); if it fails, run local Python TTS.
# If both fail, play a random clip.
TTS_MS=0
if [ "$IS_REMOTE" = true ]; then
    REMOTE_FILE="/tmp/$(basename "$OUTFILE")"
    if curl -sf -G "http://100.90.252.116:7865/speak_stream" \
        --data-urlencode "text=$SPOKEN" \
        --data-urlencode "instruct=speak clearly" \
        --max-time 30 \
        2>/dev/null \
        | ssh "${TARGET_SSH}" "cat > '${REMOTE_FILE}'" \
        && ssh "${TARGET_SSH}" "[ -s '${REMOTE_FILE}' ]"; then
        TTS_MS=0
    # elif TTS_RESPONSE=$(uv run "$SCRIPT_DIR/tts_server/tts_server.py" \
    #     --oneshot \
    #     --text "$SPOKEN" \
    #     --output "$OUTFILE" \
    #     --instruct "speak clearly" 2>/dev/null); then
    #     TTS_MS=$(echo "$TTS_RESPONSE" | jq -r '.tts_ms // 0')
    #     scp -q "$OUTFILE" "${TARGET_SSH}:${REMOTE_FILE}"
    else
        play_random
        exit 0
    fi
else
    if curl -sf -G "http://100.90.252.116:7865/speak_stream" \
        --data-urlencode "text=$SPOKEN" \
        --data-urlencode "instruct=speak clearly" \
        --max-time 30 \
        -o "$OUTFILE" 2>/dev/null && [ -s "$OUTFILE" ]; then
        TTS_MS=0
    # elif TTS_RESPONSE=$(uv run "$SCRIPT_DIR/tts_server/tts_server.py" \
    #     --oneshot \
    #     --text "$SPOKEN" \
    #     --output "$OUTFILE" \
    #     --instruct "speak clearly" 2>/dev/null); then
    #     TTS_MS=$(echo "$TTS_RESPONSE" | jq -r '.tts_ms // 0')
    else
        play_random
        exit 0
    fi
fi

jq -nc \
    --arg ts "$(date -Iseconds)" \
    --argjson payload "$PAYLOAD" \
    --arg context "$CONTEXT" \
    --arg spoken "$SPOKEN" \
    --argjson tts_ms "$TTS_MS" \
    '{ts: $ts, payload: $payload, context: $context, spoken: $spoken, tts_ms: $tts_ms}' >> "$LOG"

if [ "$IS_REMOTE" = true ]; then
    ssh "${TARGET_SSH}" "afplay -v '${CLAUDE_TTS_VOLUME:-1.7}' '${REMOTE_FILE}'"
else
    afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "$OUTFILE"
fi
