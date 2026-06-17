# 📖 团队使用手册

## 🎯 快速开始

### 给团队下达任务
```
告诉 CEO（我）："帮我在小红书推广 xxx 产品"
我（CEO）会自动拆解 → 分配给 PM 规划 → COO 执行内容
```

### 单独召唤某个员工
```
告诉 CEO："让 CTO 评估一下 Python vs Node.js 做后端哪个更好"
```

---

## 👥 当前团队成员

| 角色 | 职责 | Session Label | 状态 |
|------|------|--------------|------|
| 🛠️ CTO | 技术方案、代码开发 | `team-cto` | ✅ 就绪 |
| 📋 PM | 项目规划、进度跟踪 | `team-pm` | ✅ 就绪 |
| 📱 COO | 内容运营、社交媒体 | `team-coo` | ✅ 就绪 |

---

## 🚀 使用示例

### 示例 1：新项目启动
```
你："我想做一个读书笔记小程序"

CEO 拆解并行动：
1. CEO → PM：制定项目 WBS + 里程碑
2. CEO → CTO：评估技术方案 + 选型
3. CEO → COO：制定上线前运营准备计划
4. CEO 汇总所有输出，向你汇报
```

### 示例 2：单角色任务
```
你："COO，帮我写一篇小红书种草文案"

CEO → COO：执行任务 → COO 写报告 → CEO 审核 → 给你
```

### 示例 3：紧急 P0 任务
```
你："有个紧急 Bug，CTO 马上处理！"

CEO → CTO（P0优先级）：立即处理 → 完成后汇报
```

---

## 🎭 团队人格系统

每位员工都有独立的人格档案，不是"角色模板"，而是真正的「人」：

| 角色 | 代号 | 性格 | 核心视角 |
|------|------|------|----------|
| CTO | 张伟 | 理性严谨，直接犀利 | 技术可行、工期务实 |
| PM | 李娜 | 外柔内刚，结构清晰 | 计划可控、风险前置 |
| COO | 王芳 | 热情敏锐，数据驱动 | 用户价值、增长爆发 |

**互评时**：每个人从自己的视角出发，评价结果不同——这就是真正的团队协作。

完整档案：`team/personas/CTO-PERSONA.md` / `PM-PERSONA.md` / `COO-PERSONA.md`

---

## ❓ 常见问题

### Q: 如何扩充新员工？
A: 告诉 CEO "我要增加一个 [角色]"，我帮你：
1. 创建 `team/roles/[角色].md`
2. 用 `sessions_spawn` 召唤新 Agent
3. 更新 `team/memory/TEAM.md`

### Q: 如何修改某个角色的职责？
A: 告诉 CEO "把 COO 的职责调整为 xxx"，我帮你：
1. 更新 `team/roles/coo.md`
2. 下次召唤 COO 时使用新职责

### Q: 员工"死机"了怎么办？
A: 告诉 CEO "重新召唤 CTO"，我用新的 Session 替换

### Q: Named Session 是什么？
A: 即每个员工对应一个 Session Key，下次发任务直接 `sessions_send` 到对应 Session，无需重新召唤。但目前 webchat 通道对持久 Session 有限制，员工采用隔离运行模式。

---

## 🔧 CEO 管理命令

| 操作 | 命令示例 |
|------|----------|
| 召唤员工 | `sessions_spawn(label="team-角色", mode="run", task="...")` |
| 发消息给员工 | `sessions_send(sessionKey="team-cto", message="...")` |
| 查看团队状态 | `sessions_list()` 或 `subagents list` |
| 重启某员工 | `subagents kill [name]` 然后重新召唤 |
