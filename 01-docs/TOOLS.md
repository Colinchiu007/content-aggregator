# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

### Knowledge Base (llm-wiki)

- **Default wiki path**: `E:\Data\01-wiki-project-personal`
- **Content**: 个人知识库（笔记、读书、杂项）
- **llm-wiki skill**: `C:\Users\邱领\.openclaw\skills\llm-wiki\`
- 操作时无需手动指定路径，默认使用 E 盘知识库

### 有道云笔记 CLI
- **路径**: `C:/users\邱领\AppData\Local\youdaonote.exe`
- **不在 PATH 中**，必须用完整路径调用
- **API Key 脚本**: `D:\Program Files\QClaw\resources\openclaw\config\skills\youdaonote\get-token.ps1`

### 代理配置

- **代理端口**：`7892`（永久固定）
- **Git 全局代理已配**：`git config --global http.proxy http://127.0.0.1:7892`
- **环境变量已在 PowerShell Profile 中设置**：`HTTP_PROXY` / `HTTPS_PROXY` = `http://127.0.0.1:7892`
  - 对其他工具（curl、Python requests 等）也生效
  - 新开终端自动加载
- **Profile 路径**：`C:\Users\邱领\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`
- **旧端口已废弃**：不再使用 7890 和 12334

### Python

- **Version**: 3.12.10
- **Path**: `C:\Users\邱领\AppData\Local\Programs\Python\Python312`
- PATH 已修复，需重启终端全局生效

### 新建 Agent 必带技能

创建新 Agent 时，skills 列表中必须包含以下通用技能（除业务专属技能外）：
- `youdao-note-export` — 有道云笔记导出
- `youdaonote` — 有道云笔记管理
- （后续新增通用技能在此补充）

Add whatever helps you do your job. This is your cheat sheet.
