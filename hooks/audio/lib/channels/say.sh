#!/usr/bin/env bash
# say.sh — 系統原生語音。吃 stdin。dual source/CLI。
CH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$CH_DIR/../config.sh"

say_speak() {
    local text; text="$(cat)"; [ -z "$text" ] && return 1
    local platform="${VOICE_PLATFORM:-$(detect_platform)}"
    case "$platform" in
        mac)
            if [ -n "${VOICE_SAY_DRYRUN:-}" ]; then echo "say $text"; return; fi
            printf '%s' "$text" | say ;;
        wsl|windows)
            # 撇號跳脫:PowerShell 單引號字串把 ' 變 ''
            local safe="${text//\'/\'\'}"
            if [ -n "${VOICE_SAY_DRYRUN:-}" ]; then echo "System.Speech: $safe"; return; fi
            # SpeakAsync + 背景化:不阻塞 hook(否則 Stop hook 會卡到唸完,實測~6s)
            # Sleep 15:保活到唸完;LLM 常超出 5-8 字上限,8s 會截斷長句
            powershell.exe -NoProfile -Command "Add-Type -AssemblyName System.Speech; \$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; \$s.SpeakAsync('${safe}') | Out-Null; Start-Sleep -Seconds 15" >/dev/null 2>&1 &
            ;;
        *) return 1 ;;
    esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then say_speak; fi
