#!/usr/bin/env bash
# voice_notify.sh — Generate a contextual TTS notification to get the user's attention.
# Called by the Notification hook. Reads hook JSON from stdin.

set -euo pipefail

# Toggle: "generated" = Gemini + TTS on the fly, "random" = pick from pre-recorded clips
MODE="${CLAUDE_VOICE_MODE:-generated}"

if [ "$MODE" = "random" ]; then
  afplay "$(ls "$HOME/.claude/_voices/"*.mp3 | awk 'BEGIN{srand()} {a[NR]=$0} END{print a[int(1+rand()*NR)]}')"
  exit 0
fi

VOICE_DIR="$HOME/.claude/_voices/generated"
mkdir -p "$VOICE_DIR"

# Read hook payload
PAYLOAD=$(cat)
LOG="$HOME/.claude/_logs/voice_notify_payloads.log"
MESSAGE=$(echo "$PAYLOAD" | jq -r '.message // "Something happened"')
NOTIFICATION_TYPE=$(echo "$PAYLOAD" | jq -r '.notification_type // "unknown"')
TRANSCRIPT=$(echo "$PAYLOAD" | jq -r '.transcript_path // ""')

# Extract last assistant message from transcript
CONTEXT=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  CONTEXT=$(tail -30 "$TRANSCRIPT" \
    | jq -r 'select(.type == "assistant") | [.message.content[] | select(.type == "text") | .text] | join(" ")' 2>/dev/null \
    | tail -1 \
    | cut -c1-300)
fi

# Generate a short spoken alert via gemini
PROMPT="Turn this CLI notification into a spoken alert. Max 6 words. Snarky. No quotes, no emoji, no markdown. Just the sentence. Reference what the user is actually working on.

Type: $NOTIFICATION_TYPE
Message: $MESSAGE
Recent conversation: $CONTEXT"

SPOKEN=$(echo "" | gemini -m gemini-2.5-flash-lite -p "$PROMPT")

# Filename: sanitized text + timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
SAFE_NAME=$(echo "$SPOKEN" | tr -cd '[:alnum:] ' | tr ' ' '_' | cut -c1-60)
OUTFILE="$VOICE_DIR/${TIMESTAMP}_${SAFE_NAME}.mp3"

# Generate TTS and play
TTS_START=$(python3 -c 'import time; print(int(time.time()*1000))')
uv run https://raw.githubusercontent.com/CJHwong/toolkit/main/python/qwen3_tts.py speak --small -i "speak clearly" --output "$OUTFILE" "$SPOKEN"
TTS_MS=$(( $(python3 -c 'import time; print(int(time.time()*1000))') - TTS_START ))

# Log payload, context, generated text, and TTS duration
jq -nc \
  --arg ts "$(date -Iseconds)" \
  --argjson payload "$PAYLOAD" \
  --arg context "$CONTEXT" \
  --arg spoken "$SPOKEN" \
  --argjson tts_ms "$TTS_MS" \
  '{ts: $ts, payload: $payload, context: $context, spoken: $spoken, tts_ms: $tts_ms}' >> "$LOG"

afplay "$OUTFILE"
