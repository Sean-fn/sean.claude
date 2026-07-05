# Voice Notify — 可配置的多平台多通道通知系統

**日期**: 2026-07-05
**狀態**: 設計定案,待實作
**取代**: 現行 `~/.claude/hooks/audio/voice_notify.sh`(306 行單檔,WSL-only 硬編碼)

---

## 1. 問題陳述

現行 `voice_notify.sh` 有三個結構性缺陷:

1. **平台硬編碼**:整份腳本假設 WSL + Windows 播放。macOS 原版靠 `afplay`/`say`/`gemini`,在這台全部不存在;WSL 版把播放硬綁 powershell。無法「一份腳本、雙端通用」。
2. **Provider 硬編碼且已失效**:第 267 行寫死 `ollama run gemma3:4b-cloud`,但這台**沒裝 ollama**——文字生成每次必失敗、退回隨機音檔。唯一在線的 LLM CLI 是 `copilot`。
3. **單通道**:只能本機出聲。人不在電腦前就完全收不到通知。

## 2. 目標

- **可配置**:設定檔定義預設,環境變數可臨時覆蓋。
- **多平台**:自動偵測 mac / wsl / windows / linux,各套對應行為。
- **可插拔 provider**:Gemini / Ollama / Copilot 用同一個 command-template 機制,新增第四個只加一行 config。
- **多路廣播**:一次通知可同時走多個通道(本機語音 + Telegram 文字)。
- **OS 無關備援**:Telegram 純文字推播,不依賴任何作業系統。
- **不吵**:人在電腦前時,Telegram 靜音(閒置自動偵測)。

## 3. 非目標(YAGNI)

- 不做常駐 daemon / HTTP 介面(過度工程,場景是低頻通知)。
- 不做「只偵測單一終端互動」的 idle(技術受限,見 §7)。
- 不做 GUI 設定介面。

---

## 4. 架構:模組化拆檔(方案 B)

```
~/.claude/hooks/audio/
├── voice_notify.sh              # 入口,~40 行:載入 config → 生成文字 → 廣播
├── notify.config.json          # 預設設定(進 git,可同步)
├── channels/telegram/
│   └── notify.env              # secrets: BOT_TOKEN + CHAT_ID (chmod 600, gitignored)
└── lib/
    ├── config.sh               # 讀 config + env 覆蓋 + detect_platform()
    ├── providers.sh            # gemini / ollama / copilot 的 command template
    ├── player.sh               # 唯一知道「這台 OS 怎麼把 mp3 發聲」的單元
    └── channels/
        ├── say.sh              # 系統原生語音:mac→say、wsl/win→System.Speech、linux→略過
        ├── tts.sh              # 你的 tts_server:文字→mp3→player
        ├── fixed_audio.sh      # 播現成/隨機 mp3(fallback 用)
        └── telegram.sh         # curl Telegram Bot API 送文字
```

### 4.1 單元契約

每個單元一句話講清:做什麼、怎麼用、依賴什麼。

| 單元 | 做什麼 | 輸入 → 輸出 | 依賴 |
|------|--------|-----------|------|
| `voice_notify.sh` | 編排 | hook JSON (stdin) → 副作用 | lib/* |
| `config.sh` | 提供設定值 + 平台 | — → 環境變數 | uname, `$WSL_DISTRO_NAME` |
| `providers.sh` | prompt → 一句文字 | `$PROMPT` → stdout | copilot/gemini/ollama |
| `player.sh` | 把 mp3 發聲 | 檔案路徑 → 聲音 | ffplay/afplay/powershell |
| `say.sh` | 系統原生唸出 | 文字 (stdin) → 聲音 | say / System.Speech |
| `tts.sh` | 文字轉語音再播 | 文字 (stdin) → 聲音 | tts_server + player.sh |
| `fixed_audio.sh` | 播音檔 | 檔案路徑 → 聲音 | player.sh |
| `telegram.sh` | 送文字到手機 | 文字 (stdin) → HTTP | curl + notify.env |

### 4.2 核心設計原則

**channel 決定「播什麼」,player 決定「怎麼發聲」。** `fixed_audio` 和 `tts` 都以「發出一個 mp3」收尾,但兩者都**不自己實作播放**——都呼叫 `player.sh`。平台相關的播放複雜度全部收斂在 `player.sh` 一處。(這個共用在現行腳本裡已隱性存在:`play_random` 和 tts 的 `OUTFILE` 呼叫同一個 `play_audio`。)

**每個 channel 吃 stdin、做一件事、回 exit code。** 因此可單獨測試,且廣播器只看成功/失敗,不管內部實作。

---

## 5. 平台偵測

### 5.1 四種平台身份

「系統語音能力」把平台切成四格,**WSL 必須獨立於純 Linux**(WSL 能借 Windows 的 System.Speech,純 Linux 不能):

| 偵測結果 | 播放 (player) | 系統語音 (say) | 判定條件 |
|---------|--------------|---------------|---------|
| `mac` | afplay | `say` | `uname` = Darwin |
| `wsl` | ffplay(退 powershell) | System.Speech via powershell.exe | `$WSL_DISTRO_NAME` 非空 |
| `windows` | powershell MediaPlayer | System.Speech | uname 含 MINGW/MSYS/CYGWIN |
| `linux` | ffplay / mpg123 | **無 → say 略過** | uname = Linux 且非 WSL |

### 5.2 偵測實作(env-var 快路 + `/proc/version` 兜底)

實測數據(這台):
- 讀 `$WSL_DISTRO_NAME` env var:**0.017 ms/次**(快路)
- `grep /proc/version`:**10.6 ms/次**(兜底,慢但永遠正確)

**關鍵**:`$WSL_DISTRO_NAME` 由 WSL init 自動注入 PID 1、子行程繼承,**不來自任何 shell profile**(已 grep 確認 `.bashrc`/`.profile`/`/etc/environment` 皆無)。因此 Claude hook(子行程)繼承得到,正常情境可靠。

**但它在清空環境下會消失**——`cron`、`sudo`(無 `-E`)、`env -i` 都會讓 env var 為空,導致 WSL 被**誤判為純 linux → say 通道被略過 → 系統語音沉默退化**(最難查的那種 bug)。`/proc/version` 是 kernel 介面而非環境變數,任何情境都讀得到(實測 `env -i` 下仍含 microsoft)。

因此偵測必須是**快路 + 兜底兩層**,不是二選一:

```
detect_platform():
  [ uname = Darwin ]                              → mac
  [ $WSL_DISTRO_NAME 非空 ]                        → wsl      # 快路 0.017ms,涵蓋常態
  [ uname = Linux 且 /proc/version 含 microsoft ]  → wsl      # 兜底,env 被清空時救場
  [ uname = Linux ]                               → linux
  [ uname 含 MINGW/MSYS/CYGWIN ]                   → windows
```

env var 命中即走人;僅當它意外空掉才付 10ms 讀 `/proc/version`。快而不脆。

**單次 export**:`config.sh` 開頭 `export VOICE_PLATFORM=$(detect_platform)` 一次,後續 player/say 全讀這個變數,不重跑。一次 hook 觸發只偵測一次。

### 5.3 命名空間

所有環境變數用 `VOICE_` 前綴(沿用現有 `VOICE_SOURCE` 家族),避免與其他專案撞名。**不使用裸名 `PLATFORM`**——太通用,會與 CI/build 工具撞車。內部變數 `VOICE_PLATFORM`,對外覆蓋 `VOICE_PLATFORM_OVERRIDE`。

---

## 6. 配置

### 6.1 `notify.config.json`(進 git、可同步、無 secrets)

```json
{
  "provider": "copilot",
  "providers": {
    "copilot": { "cmd": ["copilot", "-m", "gpt-5.4-mini", "-p", "{PROMPT}"] },
    "gemini":  { "cmd": ["gemini", "-m", "gemini-2.5-flash-lite", "-p", "{PROMPT}"] },
    "ollama":  { "cmd": ["ollama", "run", "gemma3:4b-cloud", "{PROMPT}"] }
  },
  "channels": {
    "mac":     ["say", "telegram"],
    "wsl":     ["say", "telegram"],
    "windows": ["say", "telegram"],
    "linux":   ["tts", "telegram"]
  },
  "tts": {
    "ssh_host": "lab-r2",
    "speaker": "Aiden",
    "instruct": "speak dryly, flat affect"
  },
  "telegram": {
    "idle_threshold_sec": 180,
    "idle_query_fail_mode": "push"
  },
  "volume": 0.85
}
```

### 6.2 覆蓋優先級

`env > config > 內建預設`。任何欄位可被 env 臨時覆蓋:

```bash
VOICE_PROVIDER=gemini VOICE_CHANNELS=say bash voice_notify.sh
```

範例:subagent 想安靜只發 telegram → `VOICE_CHANNELS=telegram`,不動 config。

### 6.3 Provider 可插拔

三個 provider 全是「CLI 吃 prompt、吐文字」的同一形狀:

| Provider | 呼叫 |
|----------|------|
| Copilot | `copilot -m gpt-5.4-mini -p "$PROMPT"` |
| Gemini | `gemini -m ... -p "$PROMPT"` |
| Ollama | `ollama run <model> "$PROMPT"` |

`providers.sh` 讀 `providers.<name>.cmd` 陣列,把 `{PROMPT}` 佔位符換成實際 prompt 再執行。新增 provider = config 加一個 entry,**不改程式**。

**預設 `copilot`**:實測這台 `copilot` ✓ 有裝、`gemini`/`ollama` ✗ 沒裝。`--model`/`-p` 旗標實測有效。

**實作期驗證點**:`gpt-5.4-mini` 這個 model 名 CLI 不會預檢(`--help` 範例只列到 `gpt-5.4`)。首次跑實際腳本時須確認此 model 名有效 —— 若無效,copilot 會靜默失敗、每次退隨機音檔(即現行 ollama 坑的翻版)。驗證方式:`VOICE_PROVIDER=copilot bash lib/providers.sh "hi in 5 words"` 應吐出一句文字而非錯誤。

---

## 7. Telegram 通道與閒置自動開關

### 7.1 為何要開關

人在電腦前時,本機已經出聲,Telegram 再推就是重複打擾。目標:**離開座位才推,回到座位自動靜音,且零手動操作。**

### 7.2 閒置偵測(方案 A)

WSL 可呼叫 Windows `user32.dll` 的 `GetLastInputInfo`,取得**整台 Windows 最後一次鍵鼠活動**的間隔。實測可行:`idle=9.9s`。

```
telegram.sh 推播前:
  idle = 查 Windows LastInputInfo (經 powershell.exe)
  if idle < idle_threshold_sec (預設 180):   人在 → 不推,return 0
  else:                                       人不在 → 推播
```

### 7.3 判定範圍(技術限制,已接受)

`LastInputInfo` 是**系統級**——測的是整台機器,無法只鎖單一終端。因此「你在用瀏覽器/VSCode」也算人在。這符合直覺:人在座位上就不該被吵。「只偵測終端互動」技術上做不到,列為非目標。

### 7.4 邊界情況

- **查詢失敗**:`idle_query_fail_mode` 預設 `"push"`——查不到 idle 就照推。理由:漏通知比多通知糟。
- **非 WSL/Windows 平台**:純 Linux/Mac 無 `GetLastInputInfo`。這些平台的 idle 偵測列為後續增強(mac 有 `ioreg`,Linux 有 `xprintidle`),初版在非 Windows 平台 telegram **一律推**(等同 fail_mode=push)。
- **關閉自動開關**:設 `idle_threshold_sec: -1`(哨兵值)= 完全跳過 idle 查詢、永遠推。注意不能用 `0`——那會讓 `idle < 0` 恆為偽、變成永遠不推,語意相反。

### 7.5 Secrets 管理

`channels/telegram/notify.env`(chmod 600,gitignored):

```bash
TELEGRAM_BOT_TOKEN=123456:AA...
TELEGRAM_CHAT_ID=987654321
```

`telegram.sh` source 它。缺 token → 略過 telegram(不 crash)。
**須新增 `.gitignore` 規則**:`.gitignore` 現只擋 `.env`,不擋 `notify.env`,要補一條。

### 7.6 發送

```bash
curl -sf "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
     --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
     --data-urlencode "text=${SPOKEN}" --max-time 10
```

不依賴現有 `telegram` MCP plugin——那個 plugin 管 **inbound** 存取控制,這裡要的是 **outbound** 純發送,直接用 Bot API。

---

## 8. 資料流

```
hook 觸發 (Notification / Stop) — stdin = hook JSON
        ▼
voice_notify.sh
  1. config.sh   載入 config → 套 env 覆蓋 → 偵測平台(export VOICE_PLATFORM 一次)
  2. 解析 payload  抽 message、transcript 末段當 context(沿用現行邏輯)
  3. providers.sh  組 prompt → 跑選定 CLI → $SPOKEN(失敗則留空,記 log,不中斷)
  4. broadcast    依 channels[$VOICE_PLATFORM] 逐條分派 $SPOKEN
        ├─ say.sh        → mac:say / wsl,win:System.Speech / linux:略過
        ├─ tts.sh        → tts_server 產 mp3 → player.sh
        ├─ fixed_audio   → player.sh(fallback)
        └─ telegram.sh   → 查 idle → 人不在才 curl Bot API
```

### 8.1 System.Speech 阻塞注意

實測 `.Speak()` **同步阻塞至唸完**(範例句 6 秒)。若 hook 同步等待,會卡住 Claude 的 Stop hook。`say.sh` 在 wsl/windows 分支須背景化(`SpeakAsync` 或 shell `&`),避免拖住 hook。**實作重點,須驗證。**

---

## 9. 錯誤處理

**核心原則:通知系統永不 crash 掉 hook。** 任何一環壞掉,最差是「少一個通道」,絕不 `exit 1` 讓 Claude hook 報錯。

| 失敗點 | 行為 | 記 log |
|--------|------|--------|
| config 檔缺失 | 用內建預設值繼續 | 是 |
| provider CLI 掛 | `$SPOKEN` 留空 → 見分流 | 是 |
| 某條 channel 失敗 | 只跳過該條,其他照跑 | 是 |
| player 播放失敗 (ffplay) | fallback 到 powershell | 是 |
| say 在 linux | 回非零,廣播器略過 | 是 |
| Telegram token 缺 | 略過 telegram | 是 |
| idle 查詢失敗 | 依 fail_mode(預設照推) | 是 |

### 9.1 `$SPOKEN` 空(生成失敗)時的分流

生成失敗指 provider CLI 掛掉、`$SPOKEN` 為空。此時各通道:

- `say` / `tts` → 該通道無文字可唸,改由 `fixed_audio` 播隨機音檔(每次觸發最多一則,避免多通道各播一次重疊)
- `telegram` → 送**原始 hook message**(payload 的 message 欄),保證手機收得到

注意這與「通道自身失敗」不同:若 `$SPOKEN` 有值但 `say` 執行失敗(如 System.Speech 出錯),該通道只記 log 略過,**不**觸發 fixed_audio 兜底——避免把「單通道故障」放大成「全體重播」。

---

## 10. 測試策略

方案 B 的紅利:每個單元可獨立驗。

```bash
# 每條 channel 單測
echo "測試" | bash lib/channels/telegram.sh          # 手機該收到
echo "測試" | bash lib/channels/say.sh               # 系統語音該出聲
echo "測試" | bash lib/channels/tts.sh               # tts_server 該出聲
bash lib/player.sh _voices/user_action/*.mp3         # 純播放測試

# provider 單測
VOICE_PROVIDER=copilot bash lib/providers.sh "say hi in 5 words"

# 平台偵測單測
bash lib/config.sh --print-platform                  # 印出 mac|wsl|windows|linux

# idle 查詢單測
bash lib/channels/telegram.sh --print-idle           # 印出目前 idle 秒數

# 全鏈 dry-run(沿用現有旗標)
echo '{"message":"test"}' | VOICE_NOTIFY_DRY_RUN=1 bash voice_notify.sh
```

保留現有 `VOICE_NOTIFY_DRY_RUN` / `VOICE_NOTIFY_DEBUG` 旗標。

---

## 11. 遷移與清理

- 移除現行腳本裡的死碼:`say_fallback` / `say_with_notify`(呼叫不存在的 `notify_mac`)、macOS-only 殘留。由乾淨的 `say.sh` 取代。
- 現行 `_voices/` 目錄結構、`tts_server/` 全部保留沿用。
- hook 接線(`settings.json` 的 `VOICE_SOURCE=claude bash ~/.claude/hooks/audio/voice_notify.sh`)**不變**——入口路徑與傳參方式相容。

---

## 12. 決策摘要

| # | 面向 | 定案 |
|---|------|------|
| 1 | 架構 | 方案 B:主腳本 + `lib/` 模組,每 channel 一檔 |
| 2 | 播放 | `player.sh`:wsl→ffplay(退 powershell)、mac→afplay、win→powershell、linux→ffplay/mpg123 |
| 3 | 系統語音 | `say.sh` 跨平台:mac→say、wsl/win→System.Speech、linux→略過 |
| 4 | 平台偵測 | 四類 mac/wsl/windows/linux;env-var 優先(0.017ms);單次 export；變數 `VOICE_PLATFORM` |
| 5 | 配置 | `notify.config.json`(每平台一份 channel 清單)+ env 覆蓋 |
| 6 | Provider | 可插拔 cmd template,預設 copilot |
| 7 | 通道 | 多路廣播:say / tts / fixed_audio(fallback) / telegram |
| 8 | Telegram 開關 | 閒置自動偵測(方案 A),門檻 180s 可調,查失敗照推 |
| 9 | Secrets | `channels/telegram/notify.env`(chmod 600,gitignored) |
| 10 | 失敗 | 各通道獨立錯誤邊界;永不 crash hook;生成失敗→telegram 送原文、say/tts 退隨機音檔 |
