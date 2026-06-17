# 📋 完整文件清单（更新版）- PROJECT-001迁移到OpenCode

**生成时间**：2026-06-17 18:50  
**说明**：本文档列出所有需要迁移的文件，包含新导出的OpenCode格式记忆文件  
**总大小**：约 1.5 GB（86个Skill + 项目文档 + 导出文件）

---

## 📊 迁移概览（更新）

| 类别 | 文件数 | 大小预估 | 优先级 |
|------|--------|----------|--------|
| ✅ Skill（86个） | 数千个 | ~1.49 GB | ⭐⭐⭐⭐⭐ |
| ✅ PROJECT-001文档 | 27个 | ~5 MB | ⭐⭐⭐⭐⭐ |
| ✅ 代码参考架构 | 537个 | ~50 MB | ⭐⭐⭐ |
| ✅ 记忆和配置 | 21个 | ~10 MB | ⭐⭐⭐⭐⭐ |
| ✅ **OpenCode导入文件** | **3个** | **~2 MB** | ⭐⭐⭐⭐⭐ |
| **总计** | **数千个文件** | **~1.5 GB** | - |

---

## 1️⃣ Skill清单（86个）

**路径**：`C:\Users\邱领\.qclaw\workspace\migration-to-opencode\skills\`  
**大小**：约 1.49 GB  

（完整列表见上一版本文档，此处省略）

---

## 2️⃣ PROJECT-001核心文档（27个）

**路径**：`C:\Users\邱领\.qclaw\workspace\migration-to-opencode\PROJECT-001\`  
**大小**：约 5 MB  

（完整列表见上一版本文档，此处省略）

---

## 3️⃣ 代码参考架构（537个文件）

**路径**：`C:\Users\邱领\.qclaw\workspace\migration-to-opencode\reference\`  
**大小**：约 50 MB  

（完整列表见上一版本文档，此处省略）

---

## 4️⃣ 记忆和配置文件（21个）

**路径**：`C:\Users\邱领\.qclaw\workspace\migration-to-opencode\`  
**大小**：约 10 MB  

（完整列表见上一版本文档，此处省略）

---

## 5️⃣ **OpenCode导入文件（新增）**

**路径**：`C:\Users\邱领\.qclaw\workspace\migration-to-opencode\opencode-import\`  
**大小**：约 2 MB  
**说明**：记忆文件已导出为OpenCode支持的JSON格式（session + message表）

### 5.1 导出文件清单

| 序号 | 文件名 | 完整路径 | 大小 | 说明 |
|------|--------|----------|------|------|
| 1 | memory-export-full.json | `opencode-import\memory-export-full.json` | ~1.5 MB | 完整导出（16 sessions + 16 messages）|
| 2 | memory-export-recent.json | `opencode-import\memory-export-recent.json` | ~500 KB | 简化导出（最近7天）|
| 3 | README.md | `opencode-import\README.md` | ~10 KB | 导入说明文档 |

---

### 5.2 JSON格式说明

**文件结构**：

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

---

### 5.3 导出内容详情

#### 完整导出（memory-export-full.json）

- **Sessions**: 16个
  - 1个长期记忆session（MEMORY.md）
  - 15个日常记忆sessions（2026-06-01 至 2026-06-15）
- **Messages**: 16个
  - 每个session对应1个message（包含完整的记忆文件内容）
- **总大小**: ~1.5 MB

---

#### 简化导出（memory-export-recent.json）

- **Sessions**: 7个（最近7天）
  - 2026-06-09 至 2026-06-15
- **Messages**: 7个
- **总大小**: ~500 KB
- **用途**: 测试导入功能，或只需最近记忆时使用

---

### 5.4 导入到OpenCode的方法

#### 方法1：使用OpenCode导入工具（如果有）

```python
# 假设OpenCode提供了导入API
import opencode

client = opencode.Client()
client.import_memory("memory-export-full.json")
```

---

#### 方法2：手动导入（解析JSON后插入数据库）

```python
import json
import sqlite3  # 假设OpenCode使用SQLite

# 读取JSON
with open("memory-export-full.json", "r") as f:
    data = json.load(f)

# 连接到OpenCode数据库
conn = sqlite3.connect("opencode.db")
cursor = conn.cursor()

# 插入sessions
for session in data["sessions"]:
    cursor.execute(
        "INSERT OR REPLACE INTO sessions (id, user_id, start_time, end_time, metadata) VALUES (?, ?, ?, ?, ?)",
        (session["id"], session["user_id"], session["start_time"], session["end_time"], json.dumps(session["metadata"]))
    )

# 插入messages
for message in data["messages"]:
    cursor.execute(
        "INSERT OR REPLACE INTO messages (id, session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
        (message["id"], message["session_id"], message["role"], message["content"], message["timestamp"], json.dumps(message["metadata"]))
    )

conn.commit()
conn.close()
```

---

### 5.5 注意事项

1. **备份**：导入前请备份OpenCode数据
2. **去重**：如果OpenCode中已有相同ID的数据，可能需要去重
3. **格式调整**：根据实际OpenCode数据库schema调整字段名
4. **测试**：建议先导入`memory-export-recent.json`（简化版）进行测试

---

## 6️⃣ 迁移方法（不打包版本）

（内容同上一版本，此处省略）

---

## 7️⃣ OpenCode中的配置

（内容同上一版本，此处省略）

---

## 8️⃣ 验证清单

（内容同上一版本，此处省略）

---

## 9️⃣ 注意事项

（内容同上一版本，此处省略）

---

## 🔟 总结

### ✅ 已完成

1. ✅ Skill已复制到迁移目录（86个）
2. ✅ PROJECT-001文档已复制到迁移目录（27个）
3. ✅ 代码参考架构已复制到迁移目录（537个文件）
4. ✅ 记忆和配置文件已复制到迁移目录（21个）
5. ✅ **记忆文件已导出为OpenCode格式（JSON）**
6. ✅ 迁移清单文档已生成（本文档）

---

### ⏳ 待执行

1. ⏳ 将迁移目录传输到OpenCode机器
2. ⏳ 在OpenCode中放置文件
3. ⏳ **导入记忆文件（JSON）到OpenCode**
4. ⏳ 重新配置依赖和API Key
5. ⏳ 验证功能是否正常

---

### 📞 下一步

**推荐方法**：

1. **复制整个迁移目录到OpenCode**
   ```powershell
   Copy-Item -Path "C:\Users\邱领\.qclaw\workspace\migration-to-opencode" `
              -Destination "D:\OpenCode\workspace\migration\" `
              -Recurse -Force
   ```

2. **在OpenCode中导入记忆文件**
   - 将 `opencode-import\memory-export-full.json` 导入到OpenCode
   - 参考 `opencode-import\README.md` 中的说明

3. **验证导入结果**
   - 检查OpenCode是否能读取导入的记忆
   - 测试记忆检索功能

---

**文档版本**：v2.0（更新版）  
**最后更新**：2026-06-17 18:50  
**新增内容**：OpenCode导入文件（JSON格式记忆导出）  
**下一步**：将本文档和迁移目录一起传输到OpenCode机器
