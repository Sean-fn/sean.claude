#!/usr/bin/env bash
# voice_notify.sh — Generate a contextual TTS notification to get the user's attention.
# Called by the Notification and Stop hooks. Reads hook JSON from stdin.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VOICE_DIR_BASE="$SCRIPT_DIR/_voices"

# Mic check: if recording, play a subtle pop and bail — don't interrupt the call
if "$SCRIPT_DIR/mic_status" 2>/dev/null; then
    afplay "$VOICE_DIR_BASE/sound_during_mic/mixkit-long-pop-2358.wav"
    exit 0
fi

play_random() {
    local clips=("$VOICE_DIR_BASE/user_action/"*.mp3)
    afplay "${clips[RANDOM % ${#clips[@]}]}"
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

# Call the persistent TTS server; fall back to random clip if server is down
TTS_RESPONSE=$(curl -sf -G "http://localhost:7865/speak" \
    --data-urlencode "text=$SPOKEN" \
    --data-urlencode "output=$OUTFILE" \
    --data-urlencode "instruct=speak clearly" \
    --max-time 30 2>/dev/null) || { play_random; exit 0; }

TTS_MS=$(echo "$TTS_RESPONSE" | jq -r '.tts_ms')

jq -nc \
    --arg ts "$(date -Iseconds)" \
    --argjson payload "$PAYLOAD" \
    --arg context "$CONTEXT" \
    --arg spoken "$SPOKEN" \
    --argjson tts_ms "$TTS_MS" \
    '{ts: $ts, payload: $payload, context: $context, spoken: $spoken, tts_ms: $tts_ms}' >> "$LOG"

afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "$OUTFILE"
