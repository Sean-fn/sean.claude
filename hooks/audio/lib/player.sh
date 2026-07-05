#!/usr/bin/env bash
# player.sh — 唯一知道「這台 OS 怎麼把 mp3 發聲」的單元。
_run() { if [ -n "${VOICE_PLAYER_DRYRUN:-}" ]; then echo "$*"; else "$@"; fi; }

_play_linux() {
    if command -v ffplay >/dev/null 2>&1; then _run ffplay -nodisp -autoexit -loglevel quiet "$1"
    elif command -v mpg123 >/dev/null 2>&1; then _run mpg123 -q "$1"
    else return 1; fi
}

_play_powershell() {
    # 複製到 Windows %TEMP% 避開引號/UNC 地獄,再用 MediaPlayer 播。
    local file="$1" volume="${CLAUDE_TTS_VOLUME:-0.85}"
    [ -n "${VOICE_PLAYER_DRYRUN:-}" ] && { echo "powershell MediaPlayer $file"; return; }
    local wt; wt=$(powershell.exe -NoProfile -Command 'Write-Host -NoNewline $env:TEMP' 2>/dev/null | tr -d '\r'); [ -z "$wt" ] && return 1
    local wd; wd=$(wslpath -u "$wt" 2>/dev/null) || return 1
    local dest="$wd/voice_notify_play.${file##*.}"; cp -f "$file" "$dest" 2>/dev/null || return 1
    local win; win=$(wslpath -w "$dest" 2>/dev/null) || return 1
    powershell.exe -NoProfile -Command "Add-Type -AssemblyName PresentationCore; \$p=New-Object System.Windows.Media.MediaPlayer; \$p.Open([uri]'${win}'); \$p.Volume=${volume}; \$p.Play(); Start-Sleep -Milliseconds 300; while(-not \$p.NaturalDuration.HasTimeSpan){Start-Sleep -Milliseconds 50}; Start-Sleep -Seconds ([int][math]::Ceiling(\$p.NaturalDuration.TimeSpan.TotalSeconds)+1); \$p.Close()" >/dev/null 2>&1 || return 1
}

play_audio() {
    local file="$1"; [ -f "$file" ] || return 1
    case "${VOICE_PLATFORM:-linux}" in
        mac)     _run afplay "$file" ;;
        linux)   _play_linux "$file" ;;
        wsl)     _play_linux "$file" || _play_powershell "$file" ;;
        windows) _play_powershell "$file" ;;
    esac
}
