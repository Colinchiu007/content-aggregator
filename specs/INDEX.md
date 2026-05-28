# Content Aggregator 规格索引

> 最后更新: 2026-05-25

---

## 📁 文档结构

```
specs/
├── INDEX.md              ← 本文件（索引）
├── 00-system-overview.md ← 系统总览
├── 01-rewrite-processor.md ← 改写处理器详细规格
├── 02-pipeline.md       ← Pipeline 编排器规格
├── 03-web-api.md        ← Web API 规格
├── 04-export-formats.md ← 导出格式详细规格
├── 05-seo-processor.md ← SEO 处理器规格
├── 07-storage.md       ← 存储层规格
├── 10-youtube-source.md ← YouTube 数据源规格
├── 10-twitter-source.md ← Twitter 数据源规格
└── DIFF-CHECK.md        ← 差异检查清单
```

---

## 📖 阅读顺序

### 新读者
1. `00-system-overview.md` - 了解系统全貌
2. `01-rewrite-processor.md` - 理解核心改写逻辑
3. `02-pipeline.md` - 看流程如何编排
4. `03-web-api.md` - 了解对外接口

### 开发者
1. 查看 `DIFF-CHECK.md` - 检查代码与 Spec 是否一致
2. 修改代码前，先更新对应 Spec
3. 修改后，更新差异清单

---

## 🔍 快速查找

### 按主题

| 主题 | 文档 | 章节 |
|------|------|------|
| 改写策略 | `01-rewrite-processor.md` | §3 |
| 数据模型 | `00-system-overview.md` | §3 |
| API 端点 | `03-web-api.md` | §1 |
| 错误处理 | `01-rewrite-processor.md` | §6 |
| 并发控制 | `02-pipeline.md` | §10 |
| 配置格式 | `00-system-overview.md` | §8 |

### 按问题

| 问题 | 答案位置 |
|------|----------|
| 支持哪些数据源？ | `00-system-overview.md` §4.1 |
| 改写超时多久？ | `01-rewrite-processor.md` §6.2 |
| 如何自定义提示词？ | `01-rewrite-processor.md` §5.1 |
| API 返回什么格式？ | `03-web-api.md` §8 |
| 采集失败会中断吗？ | `02-pipeline.md` §8.1 |

---

## 🔄 维护指南

### 何时更新 Spec

```
✅ 新增功能时 → 先写 Spec 再开发
✅ 修改行为时 → 先更新 Spec 再改代码
✅ 发现 Bug 时 → 检查 Spec 是否需调整
❌ 不要在 Spec 中写实现细节
```

### Spec 文件命名规则

```
00-xx.md  → 系统级、全局性规格
01-xx.md  → 核心模块详细规格
02-xx.md  → 流程编排规格
03-xx.md  → 对外接口规格
10-xx.md  → 数据源详细规格（待补充）
```

---

## 📋 待补充的 Spec

| 优先级 | 文档 | 说明 |
|--------|------|------|
| 🟢 低 | `04-export-formats.md` | 导出格式详细规格 ✅ 已完成 |
| 🟢 低 | `05-seo-processor.md` | SEO 处理器规格 ✅ 已完成 |
| 🟢 低 | `06-scheduler.md` | 定时调度规格 |
| 🟢 低 | `07-storage.md` | 存储层规格 ✅ 已完成 |
| ✅ | `10-youtube-source.md` | YouTube 采集详细规格 ✅ 已完成 |
| ✅ | `10-twitter-source.md` | Twitter 采集详细规格 ✅ 已完成 |

---

## 📊 Spec 覆盖率

| 模块 | 覆盖状态 | 备注 |
|------|----------|------|
| ContentPipeline | ✅ 已覆盖 | `02-pipeline.md` |
| RewriteProcessor | ✅ 已覆盖 | `01-rewrite-processor.md` |
| ContentAPI | ✅ 已覆盖 | `02-pipeline.md` §7 |
| Web API | ✅ 已覆盖 | `03-web-api.md` |
| Exporter | ✅ 已覆盖 | `04-export-formats.md` |
| Storage Layer | ✅ 已覆盖 | `07-storage.md` |
| SEO Processor | ✅ 已覆盖 | `05-seo-processor.md` |
| RSS Collector | ⚠️ 部分 | 系统总览提及 |
| YouTube Collector | ✅ 已覆盖 | `10-youtube-source.md` |
| Twitter Collector | ✅ 已覆盖 | `10-twitter-source.md` |

---

## 🎯 下一步行动

1. **补充差异检查清单** - 在 `DIFF-CHECK.md` 中记录 Spec 与代码的差异
2. **补充数据源规格** - 为 YouTube、Twitter 等编写详细规格
3. **验证 Spec 准确性** - 通过测试确认 Spec 描述的行为是否正确
