#!/bin/bash
# mic_status exits 0 if mic is in use (kAudioDevicePropertyDeviceIsRunningSomewhere)
if ~/.claude/hooks/audio/mic_status 2>/dev/null; then
    afplay "$(dirname "$0")/_voices/sound_during_mic/mixkit-long-pop-2358.wav"
else
    afplay "$(ls "$(dirname "$0")/_voices/user_action/"*.mp3 | sort -R | head -n 1)"
fi
