# Content Aggregator API 文档 - v1.0.0

> **创建日期**：2026-06-07
> **创建人**：QClaw (CTO)
> **Base URL**：`http://localhost:8080/api`
> **协议**：HTTP/1.1，JSON 格式

---

## 一、认证方式

### 1.1 JWT Token 认证

大部分 API 需要认证，在请求头中携带 Token：

```
Authorization: Bearer {access_token}
```

### 1.2 获取 Token

**登录**获取 `access_token`（有效期 7 天）和 `refresh_token`（有效期 30 天）：

```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "your_password"
}
```

**响应**：
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

### 1.3 刷新 Token

```bash
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOi..."
}
```

---

## 二、认证模块 API

### 2.1 用户注册

```
POST /api/auth/register
```

**请求体**：
```json
{
  "username": "user@example.com",
  "password": "password123",
  "nickname": "用户昵称"
}
```

**响应**：`201 Created`
```json
{
  "id": "uuid-xxx",
  "username": "user@example.com",
  "nickname": "用户昵称"
}
```

---

### 2.2 用户登录

```
POST /api/auth/login
```

（见 [1.2 获取 Token](#12-获取-token)）

---

### 2.3 刷新 Token

```
POST /api/auth/refresh
```

（见 [1.3 刷新 Token](#13-刷新-token)）

---

### 2.4 获取当前用户信息

```
GET /api/auth/me
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "id": "uuid-xxx",
  "username": "user@example.com",
  "nickname": "用户昵称",
  "avatar": null,
  "created_at": "2026-06-01T12:00:00"
}
```

---

### 2.5 忘记密码

```
POST /api/auth/forgot-password
Content-Type: application/json

{
  "username": "user@example.com"
}
```

**响应**：`200 OK`（发送重置邮件，实际为模拟）

---

### 2.6 重置密码

```
POST /api/auth/reset-password
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "new_password": "new_password123"
}
```

**响应**：`200 OK`

---

## 三、采集模块 API

### 3.1 全源采集

```
POST /api/collect/all
Authorization: Bearer {access_token}
```

触发所有已启用的数据源采集。

**响应**：`200 OK`
```json
{
  "job_id": "uuid-xxx",
  "status": "running",
  "message": "全源采集任务已启动"
}
```

---

### 3.2 YouTube 采集

```
POST /api/collect/youtube
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "query": "关键词",
  "max_results": 10
}
```

**响应**：`200 OK`
```json
{
  "success": true,
  "collected": 10,
  "articles": [...]
}
```

---

### 3.3 URL 采集

```
POST /api/collect/url
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "url": "https://example.com/article"
}
```

**响应**：`200 OK`
```json
{
  "success": true,
  "article": {
    "id": "uuid-xxx",
    "title": "文章标题",
    "content": "...",
    "source_url": "https://example.com/article"
  }
}
```

---

### 3.4 链接采集（小红书/抖音）

```
POST /api/collect-link
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "url": "https://www.xiaohongshu.com/...",
  "platform": "xiaohongshu"
}
```

**响应**：`200 OK`
```json
{
  "success": true,
  "platform": "xiaohongshu",
  "original_text": "原文案...",
  "transcribed_text": "转写文案...",
  "article_id": "uuid-xxx"
}
```

**错误码**：
- `400`：URL 无效或平台不支持
- `500`：Cookie 失效或采集失败

---

### 3.5 抖音热榜采集

```
POST /api/collect/douyin_hot
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "success": true,
  "collected": 20,
  "articles": [...]
}
```

---

### 3.6 网易热榜采集

```
POST /api/collect/wangyi
Authorization: Bearer {access_token}
```

**响应**：`200 OK`（同 3.5）

---

### 3.7 微博热搜采集

```
POST /api/collect/weibo_hot
Authorization: Bearer {access_token}
```

**响应**：`200 OK`（同 3.5）

---

## 四、改写模块 API

### 4.1 AI 改写

```
POST /api/rewrite
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "content": "待改写文案...",
  "strategy": "DEEP_REWRITE",
  "industry": "美妆",
  "strategy_id": "custom-strategy-uuid"
}
```

**参数说明**：
- `strategy`：内置策略（`SUMMARIZE` / `STYLE_TRANSFER` / `PARAPHRASE` / `REWRITE` / `EXPAND` / `SHORT_VIDEO`）
- `industry`：可选，目标行业（如"美妆"、"金融科技"）
- `strategy_id`：可选，自定义策略 ID（优先级高于 `strategy`）

**响应**：`200 OK`
```json
{
  "success": true,
  "rewritten_content": "改写后文案...",
  "strategy_used": "DEEP_REWRITE",
  "tokens_used": 1500
}
```

---

### 4.2 获取改写策略列表

```
GET /api/rewrite-strategies
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "builtin": [
    {"id": "SUMMARIZE", "name": "摘要改写", "description": "..."},
    {"id": "REWRITE", "name": "深度改写", "description": "..."}
  ],
  "custom": [
    {
      "id": "uuid-xxx",
      "name": "小红书爆款风格",
      "description": "将文案改写为小红书爆款风格...",
      "is_default": 1,
      "created_at": "2026-06-01T12:00:00"
    }
  ]
}
```

---

### 4.3 新建自定义策略

```
POST /api/rewrite-strategies
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "小红书爆款风格",
  "description": "将文案改写为小红书爆款风格，要求：口语化、带 emoji、每段不超过 3 行",
  "is_default": 0
}
```

**响应**：`201 Created`
```json
{
  "id": "uuid-xxx",
  "name": "小红书爆款风格",
  "description": "...",
  "is_default": 0,
  "created_at": "2026-06-07T01:00:00"
}
```

---

### 4.4 更新自定义策略

```
PATCH /api/rewrite-strategies/{strategy_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "新版小红书风格",
  "description": "新的改写需求描述",
  "is_default": 1
}
```

**响应**：`200 OK`（返回更新后的策略对象）

---

### 4.5 删除自定义策略

```
DELETE /api/rewrite-strategies/{strategy_id}
Authorization: Bearer {access_token}
```

**错误码**：
- `400`：尝试删除默认策略（需先设置新默认）
- `404`：策略不存在

**响应**：`200 OK`
```json
{
  "message": "策略已删除"
}
```

---

## 五、文章管理 API

### 5.1 获取文章列表

```
GET /api/articles?page=1&page_size=20&source=rss
Authorization: Bearer {access_token}
```

**查询参数**：
- `page`：页码（默认 1）
- `page_size`：每页数量（默认 20，最大 100）
- `source`：按来源过滤（可选）
- `keyword`：按标题/内容搜索（可选）

**响应**：`200 OK`
```json
{
  "articles": [
    {
      "id": "uuid-xxx",
      "title": "文章标题",
      "source": "rss",
      "source_url": "https://...",
      "created_at": "2026-06-07T01:00:00"
    }
  ],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

---

### 5.2 获取文章详情

```
GET /api/articles/{article_id}
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "id": "uuid-xxx",
  "title": "文章标题",
  "content": "正文内容...",
  "source": "rss",
  "source_url": "https://...",
  "rewritten_content": "改写后内容...",
  "created_at": "2026-06-07T01:00:00"
}
```

---

### 5.3 删除文章

```
DELETE /api/articles/{article_id}
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "message": "文章已删除"
}
```

---

### 5.4 清空所有文章

```
POST /api/articles/clear
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "message": "已清空 100 篇文章"
}
```

---

### 5.5 导出为 PDF

```
POST /api/export/pdf
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "article_ids": ["uuid-1", "uuid-2"]
}
```

**响应**：`200 OK`（返回 PDF 文件流）
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="articles.pdf"
```

---

## 六、数据源管理 API

### 6.1 获取数据源列表

```
GET /api/sources
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "rss": [
    {
      "name": "36氪",
      "url": "https://36kr.com/feed",
      "enabled": true,
      "last_collect": "2026-06-07T00:30:00"
    }
  ],
  "hot": [
    {
      "type": "douyin",
      "name": "抖音热榜",
      "enabled": true
    }
  ]
}
```

---

### 6.2 添加 RSS 数据源

```
POST /api/sources/rss
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "新数据源",
  "url": "https://example.com/feed"
}
```

**响应**：`201 Created`
```json
{
  "name": "新数据源",
  "url": "https://example.com/feed",
  "enabled": true
}
```

---

### 6.3 删除 RSS 数据源

```
DELETE /api/sources/rss/{name}
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "message": "数据源已删除"
}
```

---

### 6.4 启用/禁用 RSS 数据源

```
POST /api/sources/rss/{name}/toggle
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "name": "36氪",
  "enabled": false
}
```

---

### 6.5 启用/禁用热榜数据源

```
POST /api/sources/hot/{source_type}/toggle
Authorization: Bearer {access_token}
```

**`source_type`**：`douyin` / `wangyi` / `weibo`

**响应**：`200 OK`（同 6.4）

---

## 七、调度管理 API

### 7.1 获取调度任务列表

```
GET /api/schedules
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "schedules": [
    {
      "job_id": "uuid-xxx",
      "name": "每小时采集",
      "schedule_type": "interval",
      "interval_minutes": 60,
      "enabled": true,
      "last_run": "2026-06-07T00:00:00",
      "next_run": "2026-06-07T01:00:00"
    }
  ]
}
```

---

### 7.2 创建调度任务

```
POST /api/schedules
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "每日采集",
  "schedule_type": "cron",
  "cron_expr": "0 9 * * *",
  "source": "all",
  "enabled": true
}
```

**`schedule_type`**：
- `interval`：按间隔执行（需 `interval_minutes`）
- `cron`：按 Cron 表达式执行（需 `cron_expr`）
- `once`：一次性执行（需 `run_at`）

**响应**：`201 Created`
```json
{
  "job_id": "uuid-xxx",
  "name": "每日采集",
  "schedule_type": "cron",
  "cron_expr": "0 9 * * *",
  "enabled": true
}
```

---

### 7.3 更新调度任务

```
PUT /api/schedules/{job_id}
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "新版每日采集",
  "enabled": false
}
```

**响应**：`200 OK`（返回更新后的任务对象）

---

### 7.4 删除调度任务

```
DELETE /api/schedules/{job_id}
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "message": "调度任务已删除"
}
```

---

### 7.5 启用/禁用调度任务

```
POST /api/schedules/{job_id}/toggle
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "job_id": "uuid-xxx",
  "enabled": false
}
```

---

### 7.6 立即执行调度任务

```
POST /api/schedules/{job_id}/run
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "message": "任务已触发",
  "run_id": "run-uuid-xxx"
}
```

---

### 7.7 查看任务执行历史

```
GET /api/schedules/{job_id}/history?limit=20
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "history": [
    {
      "run_id": "run-uuid-xxx",
      "start_time": "2026-06-07T00:00:00",
      "end_time": "2026-06-07T00:05:00",
      "status": "success",
      "articles_collected": 10
    }
  ]
}
```

---

## 八、系统配置 API

### 8.1 获取系统配置

```
GET /api/config
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": "sk-***"
  },
  "scheduler": {
    "enabled": true,
    "max_concurrent_jobs": 3
  }
}
```

> **注意**：API Key 等敏感字段会部分脱敏显示。

---

### 8.2 更新系统配置

```
PUT /api/config
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "llm": {
    "model": "gpt-4o-mini"
  },
  "scheduler": {
    "max_concurrent_jobs": 5
  }
}
```

**响应**：`200 OK`
```json
{
  "message": "配置已更新，部分配置需重启生效"
}
```

---

### 8.3 获取系统统计

```
GET /api/stats
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "total_articles": 1234,
  "today_collected": 56,
  "today_rewritten": 23,
  "storage_used": "1.2 GB",
  "uptime": "72h"
}
```

---

## 九、任务管理 API

### 9.1 获取任务列表

```
GET /api/tasks?status=running
Authorization: Bearer {access_token}
```

**`status`**：`running` / `completed` / `failed`（可选）

**响应**：`200 OK`
```json
{
  "tasks": [
    {
      "task_id": "uuid-xxx",
      "task_type": "collect",
      "status": "running",
      "progress": 60,
      "start_time": "2026-06-07T01:00:00"
    }
  ]
}
```

---

### 9.2 获取任务详情

```
GET /api/tasks/{task_id}
Authorization: Bearer {access_token}
```

**响应**：`200 OK`
```json
{
  "task_id": "uuid-xxx",
  "task_type": "collect",
  "status": "completed",
  "progress": 100,
  "result": {
    "articles_collected": 10,
    "errors": []
  },
  "start_time": "2026-06-07T01:00:00",
  "end_time": "2026-06-07T01:05:00"
}
```

---

## 十、WebSocket API

### 10.1 实时任务进度

```
WebSocket /ws
Authorization: Bearer {access_token}
```

**客户端发送**：
```json
{
  "action": "subscribe",
  "task_id": "uuid-xxx"
}
```

**服务端推送**：
```json
{
  "event": "progress",
  "task_id": "uuid-xxx",
  "progress": 60,
  "message": "正在采集第 6/10 个源..."
}
```

**事件类型**：
- `progress`：进度更新
- `completed`：任务完成
- `failed`：任务失败

---

## 十一、错误码总表

| 状态码 | 说明 | 处理建议 |
|--------|------|----------|
| `200` | 成功 | - |
| `201` | 创建成功 | - |
| `400` | 请求参数错误 | 检查请求体格式和必填字段 |
| `401` | 未授权 | 检查 Token 是否过期，重新登录 |
| `403` | 无权限 | 检查用户角色和权限 |
| `404` | 资源不存在 | 检查 ID 或路径是否正确 |
| `409` | 冲突（如用户名已存在）| 更换用户名或资源名称 |
| `429` | 请求频率过高 | 降低请求频率，使用批量化接口 |
| `500` | 服务器内部错误 | 联系管理员，查看服务器日志 |
| `503` | 服务不可用（如 LLM API 失效）| 检查外部服务状态 |

---

## 十二、数据模型

### 12.1 Article（文章）

```json
{
  "id": "uuid",
  "title": "string",
  "content": "string",
  "source": "rss | youtube | xiaohongshu | douyin | manual",
  "source_url": "string (URL)",
  "rewritten_content": "string | null",
  "strategy_used": "string | null",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

---

### 12.2 RewriteStrategy（改写策略）

```json
{
  "id": "uuid",
  "name": "string",
  "description": "string",
  "is_default": "0 | 1",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime"
}
```

---

### 12.3 Schedule（调度任务）

```json
{
  "job_id": "uuid",
  "name": "string",
  "schedule_type": "interval | cron | once",
  "interval_minutes": "integer | null",
  "cron_expr": "string | null",
  "run_at": "ISO 8601 datetime | null",
  "source": "all | rss | hot",
  "enabled": "boolean",
  "last_run": "ISO 8601 datetime | null",
  "next_run": "ISO 8601 datetime | null"
}
```

---

## 十三、示例：完整采集+改写流程

### Step 1：登录获取 Token

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user@example.com","password":"password123"}'
```

### Step 2：触发采集

```bash
curl -X POST http://localhost:8080/api/collect/all \
  -H "Authorization: Bearer {access_token}"
```

### Step 3：查看采集结果

```bash
curl http://localhost:8080/api/articles?page=1&page_size=5 \
  -H "Authorization: Bearer {access_token}"
```

### Step 4：改写文章

```bash
curl -X POST http://localhost:8080/api/rewrite \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{"content":"待改写文案...","strategy":"REWRITE","industry":"美妆"}'
```

---

## 十四、版本更新记录

| 版本 | 日期 | 修改内容 | 修改人 |
|------|------|---------|--------|
| v1.0.0 | 2026-06-07 | 初版创建，覆盖所有已有 API 端点 | QClaw (CTO) |

---

*本文档由 CTO（QClaw）撰写，符合 PRODUCT-DOCS-STANDARD v1.0.0 规范。*
