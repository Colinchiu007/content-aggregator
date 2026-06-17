# 🏢 QClaw 智能团队 — 架构说明

> 基于 OpenClaw 多 Agent 协作体系，构建类企业化运作的智能团队。

---

## 📌 团队使命

让 AI 真正像一个专业团队一样协作——有分工、有配合、有监督、有产出。

## 🏗️ 团队架构

```
         👑 主人（你）
              │
     ╔════════╧════════╗
     ║  CEO（主控台）   ║  ← 全局调度、决策、审核、汇报
     ╚════════╤════════╝
       ┌──────┼──────────┬──────────┐
       │      │          │          │
       ▼      ▼          ▼          ▼
    【CTO】 【PM】     【COO】   【Specialist】
   技术总监  项目经理    运营总监    专项专家
```

## 👥 团队成员

| 角色 | 代号 | 核心职责 |
|------|------|----------|
| 👑 CEO | `ceo` | 全局统筹、任务分解、结果审核、向你汇报 |
| 🛠️ CTO | `cto` | 技术方案、代码开发、架构设计、技术选型 |
| 📋 PM | `pm` | 项目规划、任务拆解、进度跟踪、风险管理 |
| 📱 COO | `coo` | 内容创作、社交媒体运营、用户增长 |
| 🎯 Specialist | `specialist` | 按需调用的专项专家（设计、数据分析等）|

## 📁 目录结构

```
team/
├── README.md              ← 本文件
├── config/
│   ├── structure.md       ← 详细组织架构
│   └── workflow.md        ← 工作流程规范
├── roles/
│   ├── ceo.md             ← CEO 角色定义
│   ├── cto.md             ← CTO 角色定义
│   ├── pm.md              ← PM 角色定义
│   ├── coo.md             ← COO 角色定义
│   └── specialist.md      ← Specialist 角色定义
├── tasks/
│   └── TASK.md            ← 当前任务池（所有待办/进行中/已完成）
├── reports/
│   ├── cto-report.md      ← CTO 汇报
│   ├── pm-report.md       ← PM 汇报
│   ├── coo-report.md      ← COO 汇报
│   └── summary.md         ← CEO 汇总周报
├── memory/
│   └── TEAM.md            ← 团队共享记忆（项目上下文、决策记录）
└── protocols/
    └── comm.md            ← 协作通信协议
```

## 🔄 核心工作流

```
1. 你下达指令
      ↓
2. CEO 拆解 → 分配给对应 Agent
      ↓
3. 各 Agent 并行/串行执行
      ↓
4. 各 Agent 写报告到 team/reports/
      ↓
5. CEO 汇总 + 审核
      ↓
6. 向你呈现最终结果
```


## 📝 文档协作规范

> 详细规范见 [COLLABORATION.md](./COLLABORATION.md)（跨 Session 协作规范）。

### PRD 更新流程

**问题**：别的 Agent Session（如 PM、CTO）发现新需求，怎么更新 PRD？

**方案**：使用 `INBOX.md`（需求收件箱）。

```
1. 任何 Agent（PM/CTO/Specialist）或用户 → 写 INBOX
   Path: team/projects/PROJECT-XXX/PRD/INBOX.md
2. CEO 每 4 小时检查 INBOX（Heartbeat 驱动）
3. CEO 合并到正式 PRD → 更新版本号 → 清理 INBOX
```

**为什么不用 `sessions_send`？**
- ❌ 不知道"哪个 CEO Session 在线"
- ❌ 多个 CEO Session 会冲突
- ✅ INBOX 是文件，所有 Session 都能读写

### 文件锁（防止冲突）

所有 Agent 修改共享文件前，必须先创建锁文件：

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

## 🚀 启动团队

**方式一：临时项目组（按需创建）**
```
告诉 CEO："帮我做一个 xxx 项目"
CEO 自动拆分任务 → 召唤对应 Agent → 执行 → 汇报
```

**方式二：固定团队（长期运行）**
```
为各角色创建固定 Named Session，通过 sessions_send 发指令
适合：持续性项目、日常运营任务
```

## 📖 相关文档

- [团队架构详解](config/structure.md)
- [工作流程规范](config/workflow.md)
- [各角色完整定义](roles/)
- [当前任务池](tasks/TASK.md)
- [协作通信协议](protocols/comm.md)
