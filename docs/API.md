# Content Aggregator API 文档

本文件详细列出 Web UI 提供的全部 API 端点。

---

## 基础信息

| 项目 | 值 |
|------|-----|
| 基础 URL | `http://127.0.0.1:8000` |
| 认证 | 无（内网使用） |
| 请求格式 | `application/x-www-form-urlencoded` 或 JSON |
| 响应格式 | JSON |

---

## 文章管理

### GET /api/articles
列出所有文章（JSON）

**响应示例：**
```json
[
  {
    "id": "abc123",
    "title": "文章标题",
    "source_type": "rss",
    "created_at": "2026-05-28T13:00:00"
  }
]
```

### GET /api/articles/{article_id}
获取单篇文章详情

**响应示例：**
```json
{
  "id": "abc123",
  "title": "文章标题",
  "content": "正文 Markdown...",
  "source_url": "https://example.com",
  "source_type": "rss",
  "created_at": "2026-05-28T13:00:00"
}
```

**错误响应（404）：**
```json
{ "detail": "文章不存在" }
```

### DELETE /api/articles/{article_id}
删除单篇文章

**响应（200）：**
```json
{ "success": true }
```

### POST /api/articles/clear
清空所有文章

**响应（200）：**
```json
{ "success": true }
```

---

## 配置管理

### GET /api/config
获取当前配置

**响应示例：**
```json
{
  "llm": { "provider": "deepseek", "model": "deepseek-chat" },
  "sources": { "rss": [...] },
  "export": { "output_dir": "./output/exports" },
  "scheduler": { "enabled": true, "jobs": [] }
}
```

### PUT /api/config
更新配置

**请求体（JSON）：**
```json
{
  "llm": { "model": "gpt-4o" }
}
```

**响应（200）：**
```json
{ "success": true }
```

---

## 统计信息

### GET /api/stats
获取系统统计

**响应示例：**
```json
{
  "total_articles": 42,
  "sources_enabled": 3,
  "last_collection": "2026-05-28T12:00:00"
}
```

---

## 数据源管理

### GET /api/sources
列出所有配置的数据源

**响应示例：**
```json
{
  "rss": [
    { "name": "阮一峰网络日志", "enabled": false },
    { "name": "少数派", "enabled": true }
  ],
  "youtube": [
    { "name": "UCtR5okwgTMghi_uyWvbloEg", "enabled": true }
  ],
  "twitter": [],
  "tiktok": [],
  "douyin": [],
  "xiaohongshu": [],
  "wechat": [],
  "sitemap": [
    { "name": "https://techcrunch.com/sitemap.xml", "enabled": true }
  ],
  "api": [],
  "zhihu": []
}
```

### POST /api/sources/rss
添加 RSS 数据源

**请求体（form）：**
```
name=少数派&url=https://sspai.com/feed&enabled=on
```

**响应（200）：**
```json
{ "success": true }
```

### DELETE /api/sources/rss/{name}
删除指定 RSS 数据源

**响应（200）：**
```json
{ "success": true }
```

### POST /api/sources/rss/{name}/toggle
切换 RSS 数据源启用状态

**响应（200）：**
```json
{ "success": true, "enabled": true }
```

---

## 采集任务（异步）

所有采集/改写任务均为**异步模式**，提交后返回 `task_id`，需通过轮询获取结果。

### POST /api/collect/url
采集指定 URL

**请求体（form）：**
```
url=https://sspai.com/feed&source_type=rss&rewrite=true
```

**响应（200）：**
```json
{ "task_id": "task_1779945693_3616", "status": "started" }
```

### POST /api/collect/all
采集所有已启用的数据源

**响应（200）：**
```json
{ "task_id": "task_1779945693_3617", "status": "started" }
```

### POST /api/collect/youtube
采集 YouTube 频道（需配置 API Key）

**请求体（form）：**
```
channel_id=UCtR5okwgTMghi_uyWvbloEg&max_results=10
```

**响应（200）：**
```json
{ "task_id": "task_1779945693_3618", "status": "started" }
```

---

## 改写与合成

### POST /api/compose
内容改写/合成

**请求体（form）：**
```
title=文章标题&content=正文内容&action=export&format_type=markdown
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `title` | 是 | 文章标题 |
| `content` | 是 | 正文内容（Markdown） |
| `action` | 是 | `export` = 导出文件，`rewrite` = 仅改写 |
| `format_type` | 否 | `markdown`/`html`/`txt`/`xiaohongshu`（默认 markdown） |
| `strategy` | 否 | 改写策略（见下表） |

**改写策略：**

| 策略 | 说明 |
|------|------|
| `SUMMARIZE` | 摘要提取 |
| `STYLE_TRANSFER` | 风格迁移 |
| `PARAPHRASE` | 伪原创 |
| `REWRITE` | 深度改写 |
| `EXPAND` | 内容扩展 |
| `SHORT_VIDEO` | 短视频文案 |

**响应（200）：**
```json
{ "task_id": "task_1779945858_2848", "status": "started" }
```

### POST /api/rewrite
仅改写（不导出）

**请求体（form）：** 同 `/api/compose`，`action=rewrite`

---

## 导出

### POST /api/export/pdf/{article_id}
导出文章为 PDF

**响应：** 文件流（PDF）

---

## 定时调度

### GET /api/schedules
列出所有定时任务

**响应示例：**
```json
[
  {
    "id": "047ddcde",
    "name": "debug-rss-test",
    "enabled": true,
    "schedule": { "type": "interval", "every_seconds": 3600 },
    "source": { "type": "rss", "url": "https://sspai.com/feed" },
    "last_run": "2026-05-28T13:21:33",
    "last_status": "success"
  }
]
```

### POST /api/schedules
创建定时任务

**请求体（JSON）：**
```json
{
  "name": "每小时采集少数派",
  "enabled": true,
  "schedule": { "type": "interval", "every_seconds": 3600 },
  "source": { "type": "rss", "url": "https://sspai.com/feed" },
  "keywords": ["AI", "LLM"]
}
```

**调度类型：**

| 类型 | 字段 | 说明 |
|------|------|------|
| `interval` | `every_seconds` | 间隔执行（秒） |
| `cron` | `expr` | Cron 表达式（如 `0 */2 * * *`） |
| `once` | `at` | 一次性执行（ISO 8601） |

### PUT /api/schedules/{job_id}
更新定时任务

### POST /api/schedules/{job_id}/toggle
切换任务启用状态

### POST /api/schedules/{job_id}/run
立即执行任务（不等待调度）

### DELETE /api/schedules/{job_id}
删除定时任务

### GET /api/schedules/{job_id}/history
查看任务执行历史

---

## 任务管理

### GET /api/tasks
列出所有任务

**响应示例：**
```json
[
  {
    "id": "task_1779945693_3616",
    "type": "scheduled:047ddcde",
    "description": "定时采集: debug-rss-test",
    "status": "done",
    "progress": 100,
    "message": "完成，采集 0 篇新文章",
    "result": null,
    "created_at": "2026-05-28T13:21:33.765064",
    "started_at": null,
    "finished_at": "2026-05-28T13:21:35.359948"
  }
]
```

**状态说明：**

| 状态 | 说明 |
|------|------|
| `pending` | 等待执行 |
| `started` | 执行中 |
| `running` | 执行中（别名） |
| `done` | 完成 |
| `error` | 出错 |

### GET /api/tasks/{task_id}
获取任务详情（支持轮询）

**建议轮询间隔：** 500ms ~ 1s

---

## WebSocket 实时通知

### WS /ws
实时接收任务进度通知。

**消息格式（服务器 → 客户端）：**
```json
{
  "type": "task_progress",
  "task_id": "task_1779945693_3616",
  "status": "running",
  "progress": 45,
  "message": "正在改写文章..."
}
```

**前端示例：**
```javascript
const ws = new WebSocket(`ws://${location.host}/ws`);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`任务 ${data.task_id}: ${data.progress}%`);
};
```

---

## 错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

**500 错误响应示例：**
```json
{ "detail": "错误描述" }
```
