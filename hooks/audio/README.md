# Voice Notify

把 Claude Code 的通知(Notification / Stop hook)變成語音提示 + Telegram 推播的系統。
自動偵測平台、可插拔 LLM、多通道同時廣播,且**永不 crash hook**。

## 快速開始

已經接好了 —— `settings.json` 的 Notification / Stop hook 已指向 `voice_notify.sh`,
開箱即用。手動測一發:

```bash
echo '{"message":"build finished","notification_type":"stop"}' | bash ~/.claude/hooks/audio/voice_notify.sh
```

會聽到系統語音唸出一句 AI 生成的提示。就這樣。

## 運作方式

```
hook 觸發 → 偵測平台 → LLM 生成一句提示 → 廣播到該平台的通道清單
```

四種輸出通道:

| 通道 | 做什麼 | 依賴 |
|------|--------|------|
| `say` | 系統原生語音唸出來 | mac `say` / Windows·WSL `System.Speech` |
| `tts` | 自架 TTS server 產生人聲 mp3 再播 | ssh + tts_server |
| `fixed_audio` | 播隨機預錄 mp3(備援) | ffplay / afplay / powershell |
| `telegram` | 推文字到手機 | Telegram Bot API |

平台自動偵測,無需設定:

| 偵測結果 | 預設通道 |
|---------|---------|
| mac / wsl / windows | `say` + `telegram` |
| linux(純) | `tts` + `telegram` |

## 設定

改 `notify.config.json`:

```jsonc
{
  "provider": "copilot",              // 用哪個 LLM:copilot / gemini / ollama
  "channels": {
    "wsl": ["say", "telegram"]        // 每個平台開哪些通道
  },
  "telegram": {
    "idle_threshold_sec": 180,        // 閒置超過幾秒才推 Telegram(人在電腦前就靜音)
    "idle_query_fail_mode": "push"    // 查不到閒置時的預設行為
  },
  "volume": 0.85
}
```

### 換 LLM

`provider` 改成 `gemini` 或 `ollama` 即可。要加新的?在 `providers` 加一個 entry,
`{PROMPT}` 是佔位符,不用改任何程式:

```jsonc
"providers": {
  "myLLM": { "cmd": ["mytool", "--prompt", "{PROMPT}"] }
}
```

## Telegram 設定(選用)

需要手動建一次憑證:

1. Telegram 找 **@BotFather** → `/newbot` → 拿到 bot token
2. 傳一則訊息給你的 bot,然後開 `https://api.telegram.org/bot<TOKEN>/getUpdates` 找到你的 `chat_id`
3. 建憑證檔:

```bash
cd ~/.claude/hooks/audio/channels/telegram
cp notify.env.template notify.env
# 編輯 notify.env 填入 token 與 chat_id
chmod 600 notify.env
```

`notify.env` 已被 gitignore,不會進版控。沒設定的話 Telegram 通道會自動略過(不報錯)。

### 閒置自動開關

人在電腦前(閒置 < `idle_threshold_sec`)→ 只本機出聲,Telegram 靜音。
離開座位 → 自動開始推播。門檻設 `-1` = 永遠推。

## 環境變數覆蓋

臨時改參數不用動 config(優先級 `env > config > 預設`):

```bash
VOICE_PROVIDER=gemini          bash voice_notify.sh   # 這次換 gemini
VOICE_CHANNELS=telegram        bash voice_notify.sh   # 這次只推 Telegram
VOICE_NOTIFY_DRY_RUN=1         bash voice_notify.sh   # 不出聲、只跑流程
VOICE_NOTIFY_DEBUG=1           bash voice_notify.sh   # 印 debug
```

## 測試

```bash
bash ~/.claude/hooks/audio/lib/test/run_all.sh      # 全部單元測試
```

單獨測一條通道:

```bash
echo "測試訊息" | bash ~/.claude/hooks/audio/lib/channels/telegram.sh
echo "測試訊息" | bash ~/.claude/hooks/audio/lib/channels/say.sh
bash ~/.claude/hooks/audio/lib/channels/telegram.sh --print-idle   # 印目前閒置秒數
```

## 檔案結構

```
hooks/audio/
├── voice_notify.sh          # 入口:載入 → 生成 → 廣播
├── notify.config.json       # 設定
├── channels/telegram/
│   ├── notify.env.template  # 憑證範本
│   └── notify.env           # 你的憑證(gitignored)
└── lib/
    ├── config.sh            # 平台偵測 + 設定讀取
    ├── providers.sh         # LLM 文字生成
    ├── player.sh            # mp3 播放派發
    ├── channels/            # say / tts / fixed_audio / telegram
    └── test/                # 單元測試
```

## 疑難排解

| 症狀 | 檢查 |
|------|------|
| 沒聲音 | 看 `~/.claude/_logs/voice_notify_payloads.log` 的 `channel_fail` |
| 每次都放隨機音檔 | LLM 生成失敗 —— 確認 `provider` 的 CLI 裝了且能跑 |
| Telegram 沒收到 | `notify.env` 是否填對;是否閒置未達門檻被靜音 |
| 純 Linux 沒 `tts` | `lab-r2` 需在 `~/.ssh/config`(ProxyJump 到 tts server) |
