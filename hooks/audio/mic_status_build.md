# mic_status build guide

偵測麥克風是否有任何 process 正在使用（CoreAudio HAL 層級）。

## 需求

- macOS 12+
- Xcode Command Line Tools：`xcode-select --install`

## Build

### Apple Silicon only（快速）

```bash
swiftc -framework CoreAudio \
    -o ~/.claude/hooks/mic_status \
    ~/.claude/hooks/mic_status.swift
chmod +x ~/.claude/hooks/mic_status
```

### Universal Binary（Intel + Apple Silicon）

```bash
swiftc -framework CoreAudio \
    -target arm64-apple-macos12 \
    -o /tmp/mic_status_arm64 \
    ~/.claude/hooks/mic_status.swift

swiftc -framework CoreAudio \
    -target x86_64-apple-macos12 \
    -o /tmp/mic_status_x86 \
    ~/.claude/hooks/mic_status.swift

lipo -create /tmp/mic_status_arm64 /tmp/mic_status_x86 \
    -output ~/.claude/hooks/mic_status

chmod +x ~/.claude/hooks/mic_status
```

## 驗證

```bash
# 查看架構
file ~/.claude/hooks/mic_status

# 測試回傳值（0 = mic in use, 1 = idle）
~/.claude/hooks/mic_status && echo "in use" || echo "idle"
```
