# OpenCode 记忆导入说明

## 文件说明

本目录包含从 QClaw 导出的记忆文件，已转换为 OpenCode 支持的 JSON 格式。

### 导出文件

1. **memory-export-full.json** - 完整导出（所有记忆）
   - 包含 MEMORY.md（长期记忆）
   - 包含最近15天的日常记忆
   - 总 sessions: 16
   - 总 messages: 16

2. **memory-export-recent.json** - 简化导出（最近7天）
   - 只包含最近7天的日常记忆
   - 总 sessions: 7
   - 总 messages: 7

## JSON 格式说明

```json
{
  "metadata": {
    "export_time": "2026-06-17T18:47:00",
    "source": "QClaw memory export",
    "version": "1.0",
    "total_sessions": 16,
    "total_messages": 16
  },
  "sessions": [
    {
      "id": "memory_long_term",
      "user_id": "user_qiuling",
      "start_time": "2026-04-20T00:00:00",
      "end_time": "2026-06-17T18:47:00",
      "metadata": {
        "source_file": "MEMORY.md",
        "title": "长期记忆（MEMORY.md）",
        "type": "long_term_memory"
      }
    }
  ],
  "messages": [
    {
      "id": "msg_memory_long_term_001",
      "session_id": "memory_long_term",
      "role": "system",
      "content": "...（记忆内容）...",
      "timestamp": "2026-04-20T00:00:00",
      "metadata": {
        "source": "memory_file",
        "tags": ["long_term", "memory"]
      }
    }
  ]
}
```

## 导入到 OpenCode

### 方法1：使用 OpenCode 导入工具（如果有）

```python
# 假设 OpenCode 提供了导入 API
import opencode

client = opencode.Client()
client.import_memory("memory-export-full.json")
```

### 方法2：手动导入（解析 JSON 后插入数据库）

```python
import json
import sqlite3  # 假设 OpenCode 使用 SQLite

# 读取 JSON
with open("memory-export-full.json", "r") as f:
    data = json.load(f)

# 连接到 OpenCode 数据库
conn = sqlite3.connect("opencode.db")
cursor = conn.cursor()

# 插入 sessions
for session in data["sessions"]:
    cursor.execute(
        "INSERT OR REPLACE INTO sessions (id, user_id, start_time, end_time, metadata) VALUES (?, ?, ?, ?, ?)",
        (session["id"], session["user_id"], session["start_time"], session["end_time"], json.dumps(session["metadata"]))
    )

# 插入 messages
for message in data["messages"]:
    cursor.execute(
        "INSERT OR REPLACE INTO messages (id, session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (message["id"], message["session_id"], message["role"], message["content"], message["timestamp"], json.dumps(message["metadata"]))
    )

conn.commit()
conn.close()
```

## 注意事项

1. **备份**：导入前请备份 OpenCode 数据
2. **去重**：如果 OpenCode 中已有相同 ID 的数据，可能需要去重
3. **格式调整**：根据实际 OpenCode 数据库 schema 调整字段名
4. **测试**：建议先导入 `memory-export-recent.json`（简化版）进行测试

---

**导出时间**: 2026-06-17 18:50:26
**导出工具**: QClaw Memory Export Script v1.0
