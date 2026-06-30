---
name: content-aggregator-prd
description: content-aggregator PRD.md — 产品需求文档
---

# Content Aggregator — 产品需求文档

> **版本**: v1.8.0 | **更新**: 2026-07-01
> **关联**: docs/ARCHITECTURE.md, docs/DESIGN.md

## 一、产品定位

内容聚合与 AI 改写平台：从 9 类数据源采集内容，经 AI 改写后输出标准化内容资产，支持多平台发布。

## 二、数据源

| 源类型 | 标识 | 认证 | 状态 |
|--------|------|------|------|
| RSS | `rss` | 无 | ✅ |
| YouTube | `youtube` | API Key | ✅ |
| Twitter/X | `twitter` | Bearer Token | ✅ |
| TikTok | `tiktok` | Session Cookie | ✅ |
| 抖音 | `douyin` | Cookie + Client Key | ✅ |
| 小红书 | `xiaohongshu` | Cookie + Token | ✅ |
| 微信公众号 | `wechat` | 第三方 API | ✅ |
| Sitemap | `sitemap` | 无 | ✅ |
| 自定义 API | `api` | 自定义 | ✅ |

## 三、改写策略

| 策略 | 标识 | 输出 | 耗时 |
|------|------|------|------|
| 摘要 | `summarize` | 200-500 字 | ~5s |
| 风格迁移 | `style_transfer` | 同原文长度 | ~10s |
| 伪原创 | `paraphrase` | 同义替换 | ~8s |
| 深度改写 | `rewrite` | 500-5000 字 | ~15s |
| 内容扩展 | `expand` | 3000+ 字 | ~20s |
| 短视频文案 | `short_video` | 口语化 | ~8s |

## 四、API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/collect` | POST | 采集指定源 |
| `/api/rewrite` | POST | 改写内容 |
| `/api/export` | POST | 导出文章 |
| `/api/articles` | GET | 文章列表 |
| `/api/articles/{id}` | DELETE | 删除文章 |
| `/api/tasks` | GET | 任务列表 |

## 五、非功能需求

- 单篇改写 ≤ 120s, 批量 3 并发
- SQLite ≤ 1GB
- LLM 通用 API 格式（DeepSeek/OpenAI/Qwen）
- 过滤器：DFA 敏感词 + SimHash/MinHash 去重
