# Content Aggregator 功能迭代 PRD - v1.9.0

> **创建日期**：2026-06-27  
> **创建人**：Claude  
> **审批人**：Colin Chiu  
> **状态**：已审批  
> **关联项目**：PROJECT-002（last30days 海外多源搜索集成）

---

## 一、背景与目标

### 1.1 背景

当前 content-aggregator 的采集器覆盖以**中文平台**为主（微博/抖音/小红书/微信/网易等），缺乏海外来源的覆盖能力。具体表现为：

- 中文热榜内容已可稳定采集，但国际技术/商业/文化趋势无法获取
- 缺少跨源搜索能力（用户输入任意话题后，自动在 Reddit/HN/GitHub 等平台搜索）
- 缺少跨平台互动评分体系（无法比较 Reddit upvotes 和 GitHub stars 的"热度"）

### 1.2 目标

- 新增 `last30days` 采集源类型，支持 4 个免费海外平台搜索
- 实现跨平台 engagement 归一化评分（log10 跨源可比化）
- 实现加权 RRF 融合排序
- 零配置即可用（全部使用公开免费 API）

---

## 二、需求详述

### 2.1 支持平台

| 平台 | API 类型 | 认证 | 免费额度 |
|------|---------|------|---------|
| Reddit | 公开 JSON API | 无需 | 无限制（限速 60/min） |
| Hacker News | Algolia API | 无需 | 无限制 |
| GitHub | REST API v3 | 无需 | 60 req/h（未认证） |
| Polymarket | Gamma API | 无需 | 无限制 |

### 2.2 评分引擎

评分公式：`final = 0.35*rrf + 0.25*relevance + 0.20*freshness + 0.20*engagement`

| 维度 | 权重 | 计算方式 |
|------|------|---------|
| RRF | 0.35 | Reciprocal Rank Fusion (k=60) |
| 相关性 | 0.25 | 按源内排名线性衰减 |
| 新鲜度 | 0.20 | 30 天内线性衰减 |
| 互动度 | 0.20 | log10(n+1) 归一化 |

Engagement 归一化：
- Reddit upvotes: `log10(n+1)/5.0`
- GitHub stars: `log10(n+1)/5.0`
- HN points: `log10(n+1)/5.0`
- Polymarket volume: `min(vol/100000, 1.0)`

---

## 三、实现方案

### 3.1 架构

```
用户输入话题
  → Last30DaysCollector._fetch(topic, **kwargs)
    → 并行执行：asyncio.create_task() 对每个源
      → Reddit 公开 JSON API
      → HN Algolia API
      → GitHub Issues + Repos API
      → Polymarket Gamma API
    → 收集结果
    → engagement 归一化
    → 加权 RRF 融合
    → 去重 + 排序 → 返回 list[dict]
```

### 3.2 新增文件

| 文件 | 说明 |
|------|------|
| `src/.../collectors/last30days_collector.py` | 主采集器 (380 行) |
| `backend/tests/test_last30days_collector.py` | 测试 (43 项) |

---

## 四、验收标准

- [x] 4 个免费源可并行搜索
- [x] 单一源失败不影响其他源
- [x] engagement_score 在 0-1 范围内
- [x] 按最终评分降序排列
- [x] 重复 item_id 自动去重
- [x] 未知源自动跳过并告警
- [x] 无有效源时返回空列表
- [x] 基类 collect() 错误处理正常（网络错误优雅跳过）
- [x] 43 项单元测试全部通过

---

## 五、不包含范围（后续阶段）

- X/Twitter 搜索（需 API Key）
- YouTube 搜索（需 yt-dlp）
- TikTok/Instagram 搜索（需付费 API）
- LLM 综合简报生成
- 聚类 (Cluster) 和 AI 摘要
- TrendScope UI 搜索输入框（前端改动）

---

## 六、工作量

| 阶段 | 工作量 | 完成 |
|------|--------|------|
| 采集器实现 | 1 人日 | ✅ |
| 单元测试 | 0.5 人日 | ✅ |
| 配置集成 | 0.25 人日 | ✅ |
| PRD 同步 | 0.25 人日 | ✅ |
| **合计** | **2 人日** | ✅ |
