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

# Source identifies who triggered this notification: claude | codex | subagent
VOICE_SOURCE="${VOICE_SOURCE:-claude}"

# Persona map: source → prompt style, TTS instruct string, and speaker voice.
# Use case statements for compatibility with macOS's default Bash 3.2.
prompt_style_for_source() {
    case "$1" in
        codex)
            # echo "Dry, terse, hacker tone. 5-8 words. 'Code shipped' energy. No fluff. Think git commit message energy."
            echo "Snarky Gen-Z. 5-8 words. Reference what the user is working on. You can use GEN-Z language or quirky formal tone with different emotion if suitable. REDUCE THE WORD 'seriously' BEEN USED."
            ;;
        subagent)
            echo "Brief, robotic, slightly impatient. 5-8 words. Task done. Minimal personality."
            ;;
        *)
            echo "Snarky Gen-Z. 5-8 words. Reference what the user is working on. You can use GEN-Z language or quirky formal tone with different emotion if suitable. REDUCE THE WORD 'seriously' BEEN USED."
            ;;
    esac
}

tts_instruct_for_source() {
    case "$1" in
        codex)
            echo "speak dryly, flat affect"
            ;;
        subagent)
            echo "speak quickly, neutral"
            ;;
        *)
            echo "speak clearly"
            ;;
    esac
}

tts_speaker_for_source() {
    case "$1" in
        codex)
            echo "Aiden"
            ;;
        *)
            echo "Ryan"
            ;;
    esac
}

storage_bucket_for_source() {
    case "$1" in
        codex)
            echo "codex"
            ;;
        *)
            echo "claude"
            ;;
    esac
}

# notify_mac: fires a macOS push notification locally or on the target machine via SSH
notify_mac() {
    local title="$1"
    local message="$2"
    local safe_title
    local safe_message
    safe_title=$(printf '%s' "$title" | tr '\n' ' ' | sed 's/\\/\\\\/g; s/"/\\"/g')
    safe_message=$(printf '%s' "$message" | tr '\n' ' ' | cut -c1-240 | sed 's/\\/\\\\/g; s/"/\\"/g')
    local script="display notification \"${safe_message}\" with title \"${safe_title}\""
    if [ "$IS_REMOTE" = true ]; then
        printf '%s\n' "$script" | ssh "${TARGET_SSH}" osascript >/dev/null 2>&1 || return 0
    else
        osascript -e "${script}" >/dev/null 2>&1 || return 0
    fi
}

# play_random_with_notify: fallback helper — notify which stage failed, then play a random clip
play_random_with_notify() {
    local stage="$1"
    notify_mac "Voice Notify" "Fallback to random clip [${stage}]"
    play_random
}

fixed_audio_for_source() {
    case "$1" in
        codex)
            echo "${CODEX_FIXED_AUDIO_FILE:-$VOICE_DIR_BASE/20260404_165050_Something_happened_Your_code_awaits.mp3}"
            ;;
        *)
            return 1
            ;;
    esac
}

# play_audio: plays a local file either locally or on the target machine via SSH
play_audio() {
    local file="$1"
    if [ "$IS_REMOTE" = true ]; then
        local remote_file="/tmp/$(basename "$file")"
        scp -q "$file" "${TARGET_SSH}:${remote_file}" \
            && ssh "${TARGET_SSH}" "afplay -v '${CLAUDE_TTS_VOLUME:-1.7}' '${remote_file}'" \
            || return 0
    else
        afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "$file" || return 0
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
        " || return 0
    else
        local clips=("$VOICE_DIR_BASE/user_action/"*.mp3)
        if [ ! -f "${clips[0]}" ]; then
            return 0
        fi
        afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "${clips[RANDOM % ${#clips[@]}]}" || return 0
    fi
}

# Toggle: "generated" = Gemini + TTS on the fly, "random" = pick from pre-recorded clips
MODE="${CLAUDE_VOICE_MODE:-generated}"

if [ "$MODE" = "random" ]; then
    play_random
    exit 0
fi

VOICE_STORAGE_BUCKET="$(storage_bucket_for_source "$VOICE_SOURCE")"
GENERATED_DIR="$VOICE_DIR_BASE/generated/$VOICE_STORAGE_BUCKET"
mkdir -p "$GENERATED_DIR"

LOG_DIR="$HOME/.claude/_logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/voice_notify_payloads.log"

log_note() {
    local stage="$1"
    local detail="$2"
    printf '%s\t%s\t%s\n' "$(date -Iseconds)" "$stage" "$detail" >> "$LOG" 2>/dev/null || true
}

# Read hook payload (may be empty for Stop hook)
PAYLOAD=$(cat)
if [ -z "$PAYLOAD" ]; then
    PAYLOAD='{"message":"Task complete","notification_type":"stop"}'
fi

MESSAGE=$(echo "$PAYLOAD" | jq -r '.message // .last_assistant_message // "Something happened"')
NOTIFICATION_TYPE=$(echo "$PAYLOAD" | jq -r '.notification_type // .hook_event_name // "unknown"')
TRANSCRIPT=$(echo "$PAYLOAD" | jq -r '.transcript_path // ""')

# Auto-detect source refinements from payload
SUBAGENT_TYPE=$(echo "$PAYLOAD" | jq -r '.subagent_type // ""')
if [ "$VOICE_SOURCE" = "subagent" ] && echo "$SUBAGENT_TYPE" | grep -qi "codex"; then
    VOICE_SOURCE="codex"
fi

# Temporarily bypass transcript parsing + TTS for Codex and play a fixed clip.
#FIXED_AUDIO_FILE="$(fixed_audio_for_source "$VOICE_SOURCE" || true)"
#if [ -n "$FIXED_AUDIO_FILE" ] && [ -f "$FIXED_AUDIO_FILE" ]; then
#    play_audio "$FIXED_AUDIO_FILE"
#    exit 0
#fi

PROMPT_STYLE="$(prompt_style_for_source "$VOICE_SOURCE")"
TTS_INSTRUCT="$(tts_instruct_for_source "$VOICE_SOURCE")"
TTS_SPEAKER="$(tts_speaker_for_source "$VOICE_SOURCE")"

# Extract last assistant message from transcript (JSONL format)
CONTEXT=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    CONTEXT=$(tail -30 "$TRANSCRIPT" \
        | jq -r '
            if .type == "assistant" then
                [.message.content[]? | select(.type == "text") | .text] | join(" ")
            elif .type == "response_item" and .payload.type == "message" and .payload.role == "assistant" then
                [.payload.content[]? | select(.type == "output_text" or .type == "text") | .text] | join(" ")
            else
                empty
            end
        ' 2>/dev/null \
        | awk 'NF { last = $0 } END { print last }' \
        | cut -c1-300)
fi

if [ -z "$CONTEXT" ]; then
    CONTEXT=$(echo "$PAYLOAD" | jq -r '.last_assistant_message // ""' | cut -c1-300)
fi

PROMPT="Turn this CLI notification into a spoken alert. ${PROMPT_STYLE} No quotes, no emoji, no markdown. Just the sentence. DO NOT MENTION THE WORD 'Claude' IN THE RESPONSE\n Type: $NOTIFICATION_TYPE\nMessage: $MESSAGE\nRecent conversation: $CONTEXT\n"

jq -nc \
    --arg ts "$(date -Iseconds)" \
    --arg stage "prompt_built" \
    --arg source "$VOICE_SOURCE" \
    --argjson payload "$PAYLOAD" \
    --arg context "$CONTEXT" \
    --arg prompt "$PROMPT" \
    '{ts: $ts, stage: $stage, source: $source, payload: $payload, context: $context, prompt: $prompt}' >> "$LOG" || true

if [ "${VOICE_NOTIFY_DRY_RUN:-}" = "1" ]; then
    exit 0
fi

# Health-check TTS server before burning an LLM call
if ! curl -sf --max-time 5 "http://100.90.252.116:7865/health" > /dev/null 2>&1; then
    log_note "tts_health_check_failed" "health endpoint unavailable"
    play_random_with_notify "tts_health_check"
    exit 0
fi

if [ "${VOICE_NOTIFY_DEBUG:-}" = "1" ]; then
    notify_mac "DEBUG" "PROMPT: [${PROMPT}]"
fi

# Generate spoken text via Gemini; fall back to random clip if it fails
if ! SPOKEN=$(echo "" | ollama run gemma3:4b-cloud --think=false --hidethinking "$PROMPT" 2>/dev/null) || [ -z "$SPOKEN" ]; then
    log_note "llm_generation_failed" "$SPOKEN"
    play_random_with_notify "llm_generation"
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
        --data-urlencode "speaker=${TTS_SPEAKER}" \
        --data-urlencode "instruct=${TTS_INSTRUCT}" \
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
        play_random_with_notify "tts_stream_remote"
        exit 0
    fi
else
    if curl -sf -G "http://100.90.252.116:7865/speak_stream" \
        --data-urlencode "text=$SPOKEN" \
        --data-urlencode "speaker=${TTS_SPEAKER}" \
        --data-urlencode "instruct=${TTS_INSTRUCT}" \
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
        play_random_with_notify "tts_stream_local"
        exit 0
    fi
fi

jq -nc \
    --arg ts "$(date -Iseconds)" \
    --argjson payload "$PAYLOAD" \
    --arg context "$CONTEXT" \
    --arg spoken "$SPOKEN" \
    --argjson tts_ms "$TTS_MS" \
    '{ts: $ts, payload: $payload, context: $context, spoken: $spoken, tts_ms: $tts_ms}' >> "$LOG" || true

if [ "$IS_REMOTE" = true ]; then
    ssh "${TARGET_SSH}" "afplay -v '${CLAUDE_TTS_VOLUME:-1.7}' '${REMOTE_FILE}'" || true
else
    afplay -v "${CLAUDE_TTS_VOLUME:-1.7}" "$OUTFILE" || true
fi
