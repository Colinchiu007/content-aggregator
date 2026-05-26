# Content Aggregator - 正式规格文档

> **项目**: Content Aggregator (热文采集改写)  
> **版本**: 1.0.0  
> **状态**: 已实现  
> **最后更新**: 2026-05-26---

## 1. 系统概述

### 1.1 项目定位

热文采集改写平台：将互联网多源内容（RSS/YouTube/Twitter/小红书等）采集后进行 AI 改写，输出标准化内容资产供多平台发布。

### 1.2 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端 | Python 3.12 + FastAPI |
| 前端 | Jinja2 原生模板 |
| LLM | DeepSeek / OpenAI / Qwen（可配置）|
| 存储 | SQLite |

### 1.3 核心流程

```
采集 → 过滤 → 改写 → 翻译(可选) → SEO(可选) → 格式化 → 导出
```

---

## 2. 核心模块

### 2.1 Pipeline (src/content_aggregator/workflows/pipeline.py)

负责整体流程编排，支持异步上下文管理。

**核心方法**：
- `process_url(url, rewrite, strategy, seo, limit)` → 处理单个 URL
- `process_all_sources(...)` → 批量采集所有配置的源
- `process_source(source_type, ...)` → 采集指定类型源

### 2.2 RewriteProcessor (src/content_aggregator/processors/rewrite/)

负责 AI 改写，支持多种策略。

**支持的策略**：

| 策略 | 标识 | 输出特点 |
|------|------|----------|
| 摘要提取 | `summarize` | 200-500 字 |
| 风格迁移 | `style_transfer` | 保持原文长度 |
| 伪原创 | `paraphrase` | 同义替换 |
| 深度改写 | `rewrite` | 500-5000 字 |
| 内容扩展 | `expand` | 3000+ 字 |
| 短视频文案 | `short_video` | 口语化 |

### 2.3 过滤器 (src/content_aggregator/processors/filter/)

**SensitiveFilter** - 敏感词过滤
- `strict_mode=false`: 替换敏感词
- `strict_mode=true`: 直接拦截

**DedupFilter** - 去重过滤
- 精确去重：MD5 hash
- 模糊去重：相似度检测（阈值 0.8）

### 2.4 数据源 (src/content_aggregator/sources/collectors/)

已实现的 collectors：

| 源类型 | 标识 | 认证方式 |
|--------|------|----------|
| RSS | `rss` | 无 |
| YouTube | `youtube` | API Key |
| Twitter/X | `twitter` | Bearer Token |
| TikTok | `tiktok` | Session Cookie |
| 抖音 | `douyin` | Cookie + Client Key |
| 小红书 | `xiaohongshu` | Cookie + Token |
| 微信公众号 | `wechat` | 第三方 API |
| Sitemap | `sitemap` | 无 |
| 自定义 API | `api` | 自定义 |

---

## 3. Web API

### 3.1 端点清单

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/collect` | POST | 采集指定源 |
| `/api/rewrite` | POST | 改写内容 |
| `/api/export` | POST | 导出文章 |
| `/api/articles` | GET | 文章列表 |
| `/api/articles/{id}` | DELETE | 删除文章 |
| `/api/tasks` | GET | 任务列表 |

### 3.2 请求/响应格式

```json
// POST /api/collect
{
  "source_type": "rss",
  "url": "https://...",
  "rewrite": true,
  "strategy": "rewrite",
  "seo": false
}

// 响应
{
  "success": true,
  "articles": [...],
  "count": 5
}
```

---

## 4. Web UI

### 4.1 页面清单

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 仪表盘 | 统计 + 快捷操作 |
| `/articles` | 文章列表 | 查看/搜索/删除 |
| `/sources` | 数据源 | 采集入口 |
| `/settings` | 配置 | 编辑 config.yaml |
| `/compose` | 手动输入 | 粘贴改写 |
| `/tasks` | 任务 | 异步任务状态 |
| `/scheduler` | 调度 | Cron 管理 |

### 4.2 交互约束

- 深色主题
- 响应式（支持移动）
- 异步操作：spinner
- 结果通知：Toast

---

## 5. 配置

### 5.1 必需配置

```yaml
llm:
  provider: deepseek | openai | qwen
  api_key: 必需

export:
  output_dir: 必需
```

### 5.2 可选配置

```yaml
http:
  timeout: 30
  proxy: null

filter:
  sensitive:
    enabled: true
    strict_mode: false
  dedup:
    enabled: true
    similarity_threshold: 0.8
```

---

## 6. 数据模型

### 6.1 Content（原始内容）

```python
@dataclass
class Content:
    id: str
    source_id: str
    source_type: str
    url: str
    title: str
    content: str
    summary: str
    author: str
    published_at: datetime
    metadata: dict
    raw_data: Any
```

### 6.2 Article（处理后）

```python
@dataclass
class Article:
    id: str
    title: str
    original_title: str
    source: str
    source_url: str
    author: str
    published_at: datetime
    content: str
    summary: str
    tags: list[str]
    word_count: int
    metadata: dict
```

---

## 7. 性能约束

```
单篇改写: ≤ 120 秒
批量采集: 每源 ≤ 100 篇
并发: 默认 3
网络超时: 30 秒
存储: SQLite ≤ 1GB
```

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-26 | 初始正式版，整合 4 份 Spec |
