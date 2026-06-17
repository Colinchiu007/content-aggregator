# 跨 Session 协作规范 v1.0.0

> **创建日期**：2026-06-07  
> **创建人**：QClaw (CEO)  
> **适用范围**：所有 Agent Session（CEO、CTO、PM、COO、Specialist）

---

## 一、核心原则

### 1.1 单一信任源（Single Source of Truth）

**规则**：每个"正式文档"只有一个维护者，其余 Agent **只读**或**通过收件箱提交修改建议**。

| 文档类型 | 维护者 | 其余 Agent 权限 |
|----------|--------|----------------|
| PRD | CEO | ❌ 不可直接修改，✅ 可写 INBOX |
| API 文档 | CTO | ❌ 不可直接修改，✅ 可提建议 |
| 技术设计文档 | CTO | ❌ 不可直接修改，✅ 可提建议 |
| 商业计划 | COO | ❌ 不可直接修改，✅ 可提建议 |
| 日报/周报 | CEO | 📁 所有人可追加 |

---

### 1.2 异步协作优先

**规则**：优先使用**文件**而非 `sessions_send` 进行跨 Session 协作。

**原因**：
- ✅ 文件是持久的，不依赖"对方 Session 是否在线"
- ✅ 文件有版本历史（Git）
- ❌ `sessions_send` 是即时的，对方可能不在线

**例外**（可以用 `sessions_send`）：
- 紧急需求（P0）
- 需要立即确认的问题

---

### 1.3 文件锁（防止冲突）

**规则**：修改共享文件前，先创建锁文件（`.lock`），修改完后删除。

**实现**：`team/scripts/process_inbox.py` 已有锁机制。

**所有 Agent 必须遵守**：
```python
LOCK = "path/to/.lock"
if os.path.exists(LOCK):
    print("文件被占用，稍后重试")
    exit()
open(LOCK, "w").write(str(time.time()))
try:
    # 修改文件...
    pass
finally:
    os.remove(LOCK)
```

---

## 二、各类文档的协作流程

### 2.1 PRD（产品需求文档）

**维护者**：CEO  
**路径**：`team/projects/PROJECT-XXX/PRD/PRD-vX.X.X-YYYY-MM-DD.md`

**其余 Agent 如何提交需求？**

1. **写 INBOX**（推荐 ✅）：
   ```
   1. 打开 `team/projects/PROJECT-XXX/PRD/INBOX.md`
   2. 在"## 待处理需求"章节末尾追加需求
   3. 格式：
      ## [YYYY-MM-DD HH:MM] 需求标题
      - **来源**：（PM 会话 / CTO 会话 / 用户直接提出）
      - **描述**：...
      - **优先级**：P0/P1/P2
   4. 保存文件
   ```

2. **发消息给 CEO**（紧急需求 ⚠️）：
   ```
   使用 sessions_send 发消息给 CEO Session：
   "紧急需求：XXX，请立即更新 PRD"
   ```

**CEO 如何处理？**

1. 每 4 小时检查一次 INBOX（Heartbeat 驱动）
2. 读取 INBOX，合并到 PRD
3. 更新 PRD 版本号
4. 将已处理需求移到"处理历史"

---

### 2.2 API 文档

**维护者**：CTO  
**路径**：`team/projects/PROJECT-XXX/API/API-vX.X.X-YYYY-MM-DD.md`

**其余 Agent 如何提交修改建议？**

1. 在 `team/projects/PROJECT-XXX/API/INBOX.md` 写建议（同 PRD 流程）
2. 或直接告诉 CTO Session（如果在线）

**CTO 如何处理？**

1. 每次修改代码（新增/修改 API 端点）后，立即更新 API 文档
2. 收到 INBOX 建议后，48 小时内处理

---

### 2.3 技术设计文档

**维护者**：CTO  
**路径**：`team/projects/PROJECT-XXX/TECH/TECH-vX.X.X-YYYY-MM-DD.md`

**其余 Agent 如何参与？**

1. **PM**：在 INBOX 提需求变更
2. **Specialist**：在 INBOX 提技术可行性分析
3. **CEO**：审批后通知 CTO 更新文档

---

### 2.4 商业计划 / 市场分析

**维护者**：COO  
**路径**：`team/projects/PROJECT-XXX/BUS/`

**其余 Agent 如何参与？**

1. **PM**：提供用户调研数据
2. **CTO**：提供技术成本估算
3. **CEO**：审批后通知 COO 更新文档

---

## 三、INBOX 规范

### 3.1 什么是 INBOX？

**定义**：每个"正式文档"旁边都有一个 `INBOX.md`，用于收集修改建议和新需求。

**为什么需要 INBOX？**

- ✅ 异步协作（不依赖对方在线）
- ✅ 有记录（不会丢失需求）
- ✅ 有缓冲（维护者定期处理，不被频繁打断）

---

### 3.2 INBOX 文件结构

```
team/projects/PROJECT-XXX/
├── PRD/
│   ├── PRD-v1.0.0-2026-06-01.md   # 正式 PRD（只有 CEO 修改）
│   ├── INBOX.md                      # PRD 需求收件箱
│   └── ARCHIVE/                      # 已处理需求归档
├── API/
│   ├── API-v1.0.0-2026-06-07.md   # 正式 API 文档（只有 CTO 修改）
│   └── INBOX.md                      # API 修改建议收件箱
└── TECH/
    ├── TECH-v1.0.0-2026-06-01.md  # 正式技术设计（只有 CTO 修改）
    └── INBOX.md                      # 技术建议收件箱
```

---

### 3.3 写 INBOX 的格式规范

**必须包含**：
- **时间戳**：`[YYYY-MM-DD HH:MM]`
- **需求标题**：简短描述
- **来源**：哪个 Session / 哪个人
- **描述**：详细需求说明
- **优先级**：P0（紧急）/ P1（重要）/ P2（一般）

**示例**：
```markdown
## [2026-06-07 13:30] 支持知乎专栏采集
- **来源**：用户直接提出
- **描述**：用户需要采集知乎专栏文章，用于内容参考和改写。需要新建 ZhihuCollector 类。
- **优先级**：P1
- **相关文件**：`src/content_aggregator/sources/collectors/`
```

---

### 3.4 处理 INBOX 的频率

| 文档类型 | 维护者 | 检查频率 | 处理时限 |
|----------|--------|----------|----------|
| PRD/INBOX | CEO | 每 4 小时 | 24 小时内 |
| API/INBOX | CTO | 每 8 小时 | 48 小时内 |
| TECH/INBOX | CTO | 每 8 小时 | 48 小时内 |
| BUS/INBOX | COO | 每天 1 次 | 72 小时内 |

---

## 四、跨 Session 通信规范

### 4.1 什么时候用 `sessions_send`？

**可以用**（紧急场景）：
- P0 需求（影响上线）
- 线上故障（需要立即响应）
- 用户等待响应（超过 10 分钟）

**不要用**（非紧急场景）：
- 常规需求（P1/P2）→ 写 INBOX
- 建议和想法 → 写 INBOX
- 状态同步 → 写 `memory/YYYY-MM-DD.md`

---

### 4.2 `sessions_send` 的目标 Session

**规则**：发送前，先确认目标 Session 的 `label` 或 `sessionKey`。

**如何查找？**
```python
# 列出所有可见 Session
sessions_list(kinds=["isolated", "main"], limit=20)

# 根据 label 查找
# 例如：CEO 的 label 是 "ceo-session"
sessions_send(label="ceo-session", message="紧急需求：...")
```

**如果找不到目标 Session？**
- 写 INBOX（异步，对方下次上线会看到）
- 或告诉用户，让用户转达

---

### 4.3 消息格式规范

**紧急消息**（P0）：
```
[紧急] 需求标题
- 影响：...
- 建议处理时间：...
```

**常规消息**（P1/P2）：
```
[需求建议] 需求标题
- 已写入 INBOX：`path/to/INBOX.md`
- 请有空时处理
```

---

## 五、冲突处理

### 5.1 多个 Agent 同时修改一个文件

**预防**（文件锁）：
- 修改前创建 `.lock` 文件
- 修改完删除 `.lock` 文件
- 如果 `.lock` 已存在，等待 1 分钟后重试（最多 3 次）

**发生冲突后**（Git merge conflict）：
1. 不要直接覆盖
2. 通知 CEO（或文档维护者）
3. 由维护者手动 merge

---

### 5.2 需求重复提交

**场景**：PM 和 CTO 都提交了"支持知乎采集"需求。

**处理**：
1. CEO 在合并 INBOX 时去重
2. 在 PRD 中标注"多个来源"，不遗漏任何一个

---

### 5.3 需求描述不清楚

**场景**：INBOX 里只写了"支持知乎"，没有详细描述。

**处理**：
1. CEO 在 PRD 中标注"[待澄清]"
2. 通知提出人补充细节（写 INBOX 或 sessions_send）
3. 补充后再合并到 PRD

---

## 六、工具脚本

### 6.1 `process_inbox.py`（CEO 用）

**功能**：处理 PRD INBOX，合并到 PRD。

**路径**：`team/scripts/process_inbox.py`

**使用**：
```bash
# 手动执行
python team/scripts/process_inbox.py

# 自动执行（Heartbeat 每 4 小时触发一次）
# 无需手动运行
```

---

### 6.2 `check_inbox.py`（通用）

**功能**：检查所有 INBOX，报告待处理数量。

**路径**：`team/scripts/check_inbox.py`（待编写）

**使用**：
```bash
python team/scripts/check_inbox.py
# 输出：
# PRD INBOX: 3 个待处理需求
# API INBOX: 0 个待处理建议
# TECH INBOX: 1 个待处理建议
```

---

## 七、版本更新记录

| 版本 | 日期 | 修改内容 | 修改人 |
|------|------|---------|--------|
| v1.0.0 | 2026-06-07 | 创建文档，定义跨 Session 协作规范 | QClaw (CEO) |

---

*本文档为团队规范，所有 Agent 必须遵守。*
