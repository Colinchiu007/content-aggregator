# Web API 规格

> 版本: 1.1.0  
> 最后更新: 2026-05-27  
> 状态: 已根据实际代码更新（异步任务模式）

---

## 1. API 概览

### 1.1 基础信息

- **协议**: HTTP/1.1
- **数据格式**: JSON（异步任务状态 API）
- **编码**: UTF-8
- **端口**: 8000（默认）
- **任务模式**: 长时间操作使用异步任务（返回 task_id，轮询状态）

### 1.2 端点清单

| 方法 | 路径 | 功能 | 响应模式 |
|------|------|------|----------|
| GET | `/` | 仪表盘页面 | HTML |
| GET | `/articles` | 文章列表页面 | HTML |
| GET | `/articles/{article_id}` | 文章详情页面 | HTML |
| GET | `/sources` | 数据源页面 | HTML |
| GET | `/settings` | 配置编辑页面 | HTML |
| GET | `/compose` | 手动输入页面 | HTML |
| GET | `/tasks` | 任务列表页面 | HTML |
| GET | `/scheduler` | 调度管理页面 | HTML |
| POST | `/api/collect/all` | 触发全源采集 | **异步任务** |
| POST | `/api/collect/youtube` | YouTube 采集 | **异步任务** |
| POST | `/api/collect/url` | 单 URL 采集 | **异步任务** |
| POST | `/api/rewrite` | 改写已有文章 | **异步任务** |
| POST | `/api/compose` | 手动输入 → 改写/导出 | **异步任务** |
| GET | `/api/articles/{article_id}` | 获取单篇文章 | 同步 |
| DELETE | `/api/articles/{article_id}` | 删除文章 | 同步 |
| POST | `/api/export/pdf` | 导出 PDF | **异步任务** |
| POST | `/api/articles/clear` | 清空所有文章 | 同步 |
| GET | `/api/tasks` | 获取任务列表 | 同步 |
| GET | `/api/tasks/{task_id}` | 获取任务状态 | 同步 |
| GET | `/api/sources` | 获取数据源配置 | 同步 |
| POST | `/api/sources/rss` | 添加 RSS 源 | 同步 |
| DELETE | `/api/sources/rss/{name}` | 删除 RSS 源 | 同步 |
| POST | `/api/sources/rss/{name}/toggle` | 切换 RSS 源启用状态 | 同步 |
| GET | `/api/config` | 获取配置 | 同步 |
| PUT | `/api/config` | 保存配置 | 同步 |
| GET | `/api/stats` | 获取统计信息 | 同步 |
| GET | `/api/schedules` | 获取调度任务列表 | 同步 |
| POST | `/api/schedules` | 创建调度任务 | 同步 |
| PUT | `/api/schedules/{job_id}` | 更新调度任务 | 同步 |
| DELETE | `/api/schedules/{job_id}` | 删除调度任务 | 同步 |
| POST | `/api/schedules/{job_id}/toggle` | 切换调度任务状态 | 同步 |
| POST | `/api/schedules/{job_id}/run` | 立即运行调度任务 | 同步 |
| GET | `/api/schedules/{job_id}/history` | 获取调度任务历史 | 同步 |

---

## 2. 异步任务模式

### 2.1 任务生命周期

```
客户端               服务器
  |                     |
  |-- POST /api/xxx -->|  (立即返回)
  |<-- {"task_id":..}--|
  |                     |
  |-- GET /api/tasks/id->|  (轮询状态)
  |<-- {"status":"running", "progress":50}--|
  |                     |
  |-- GET /api/tasks/id->|
  |<-- {"status":"done", "result":{...}}--|
```

### 2.2 任务状态枚举

| 状态 | 含义 |
|------|------|
| `pending` | 等待中（已创建，未开始） |
| `running` | 执行中（有 progress 和 message） |
| `done` | 已完成（有 result） |
| `error` | 失败（有 message 说明错误原因） |

### 2.3 任务对象格式

```json
{
  "id": "task-uuid",
  "type": "collect_all | rewrite | compose | export",
  "status": "running",
  "progress": 50,
  "message": "正在处理第 15 篇...",
  "result": {"article_ids": [...], "summary": {...}},  // 仅 done 时有
  "created_at": "2026-05-27T22:00:00Z",
  "updated_at": "2026-05-27T22:01:00Z"
}
```

---

## 3. 采集 API（异步）

### 3.1 POST /api/collect/all

**请求** (Form Data):
```
rewrite: true
translate: zh  (或 null)
formats: markdown,html
limit: 20
```

**响应** (立即返回):
```json
{
  "task_id": "uuid-string",
  "status": "started"
}
```

**任务完成后** (GET /api/tasks/{task_id}):
```json
{
  "id": "uuid-string",
  "type": "collect_all",
  "status": "done",
  "progress": 100,
  "message": "采集完成：3 个源成功，15 篇文章",
  "result": {
    "summary": {"total_sources": 3, "success": 3, "total_articles": 15},
    "article_ids": ["uuid-1", "uuid-2", ...]
  },
  "created_at": "2026-05-27T22:00:00Z",
  "updated_at": "2026-05-27T22:01:00Z"
}
```

### 3.2 POST /api/collect/url

**请求** (Form Data):
```
url: https://example.com/feed.xml
source_type: rss
rewrite: true
```

**响应**: 同 `/api/collect/all`（异步任务模式）

### 3.3 POST /api/collect/youtube

**请求** (Form Data):
```
search_query: AI教程
order: relevance
max_results: 10
rewrite: true
```

**响应**: 同 `/api/collect/all`（异步任务模式）

---

## 4. 改写 API（异步）

### 4.1 POST /api/rewrite

**请求** (Form Data):
```
article_id: uuid-string
strategy: REWRITE | PARAPHRASE | STYLE_TRANSFER | SUMMARIZE | EXPAND
translate: yes | no
```

**响应** (立即返回):
```json
{
  "task_id": "uuid-string",
  "status": "started"
}
```

**任务完成后** (GET /api/tasks/{task_id}):
```json
{
  "id": "uuid-string",
  "type": "rewrite",
  "status": "done",
  "progress": 100,
  "message": "改写完成",
  "result": {"article_id": "uuid-string"},
  "created_at": "2026-05-27T22:00:00Z",
  "updated_at": "2026-05-27T22:00:30Z"
}
```

### 4.2 POST /api/compose

**请求** (Form Data):
```
title: 可选标题
content: 原文内容（必填）
action: rewrite | export
format_type: markdown | html | json
strategy: REWRITE | PARAPHRASE | ...
translate: yes | no
```

**响应**: 同 `/api/rewrite`（异步任务模式）

**任务完成后 result**:
```json
{
  "path": "./output/exports/标题.md",  // action=export 时
  "article_id": "uuid-string"           // action=rewrite 时
}
```

---

## 5. 导出 API（异步）

### 5.1 POST /api/export/pdf

**请求** (Form Data):
```
article_id: uuid-string
```

**响应**: 异步任务模式，任务完成后 result: `{"path": "./output/exports/标题.pdf"}`

---

## 6. 文章管理 API（同步）

### 6.1 GET /api/articles

**查询参数**:
```
?page=1
&per_page=20
&source=rss
&search=关键词
```

**响应**:
```json
{
  "articles": [...],
  "total": 100,
  "page": 1,
  "per_page": 20,
  "total_pages": 5
}
```

### 6.2 GET /api/articles/{article_id}

**响应**:
```json
{
  "id": "uuid",
  "title": "标题",
  "original_title": "原标题",
  "content": "内容...",
  "source": "rss",
  "source_url": "https://...",
  "word_count": 2500,
  "published_at": "2026-05-27T22:00:00Z",
  "created_at": "2026-05-27T22:00:00Z",
  "metadata": {"rewritten": true, ...}
}
```

### 6.3 DELETE /api/articles/{article_id}

**响应**:
```json
{
  "success": true,
  "message": "已删除"
}
```

### 6.4 POST /api/articles/clear

**响应**:
```json
{
  "success": true,
  "message": "已清空 15 篇文章"
}
```

---

## 7. 任务 API（同步）

### 7.1 GET /api/tasks

**响应**:
```json
{
  "tasks": [
    {
      "id": "task-uuid",
      "type": "collect_all",
      "status": "running",
      "progress": 50,
      "message": "正在处理第 15 篇...",
      "created_at": "2026-05-27T22:00:00Z",
      "updated_at": "2026-05-27T22:01:00Z"
    }
  ]
}
```

### 7.2 GET /api/tasks/{task_id}

**响应**: 单个任务对象（见 2.3 节）

---

## 8. 配置 API（同步）

### 8.1 GET /api/config

**响应**:
```json
{
  "success": true,
  "config": {
    "llm": {"model": "gpt-3.5-turbo", ...},
    "sources": {...},
    "export": {...},
    "filter": {...},
    "notifications": {...}
  }
}
```

### 8.2 PUT /api/config

**请求**:
```json
{
  "config": {
    "llm": {"model": "deepseek", "api_key": "sk-xxx"}
  }
}
```

**响应**:
```json
{
  "success": true,
  "message": "配置已保存，重启后生效"
}
```

---

## 9. 数据源 API（同步）

### 9.1 GET /api/sources

**响应**:
```json
{
  "success": true,
  "sources": {
    "rss": [
      {"name": "MockRSS", "url": "https://example.com/feed.xml", "enabled": true}
    ]
  }
}
```

### 9.2 POST /api/sources/rss

**请求** (Form Data):
```
name: MyRSS
url: https://example.com/feed.xml
max_items: 10
```

**响应**:
```json
{
  "success": true,
  "message": "已添加 RSS 源"
}
```

### 9.3 DELETE /api/sources/rss/{name}

**响应**:
```json
{
  "success": true,
  "message": "已删除"
}
```

### 9.4 POST /api/sources/rss/{name}/toggle

**响应**:
```json
{
  "success": true,
  "enabled": false  // 切换后的状态
}
```

---

## 10. 调度 API（同步）

### 10.1 GET /api/schedules

**响应**:
```json
{
  "success": true,
  "schedules": [
    {
      "id": "job-uuid",
      "name": "每日采集",
      "schedule": {"kind": "cron", "expr": "0 9 * * *"},
      "enabled": true,
      "last_run": "2026-05-27T09:00:00Z",
      "next_run": "2026-05-28T09:00:00Z"
    }
  ]
}
```

### 10.2 POST /api/schedules

**请求**:
```json
{
  "name": "每日采集",
  "schedule": {"kind": "cron", "expr": "0 9 * * *"},
  "payload": {"rewrite": true, "formats": ["markdown"]}
}
```

**响应**:
```json
{
  "success": true,
  "message": "调度任务已创建",
  "job_id": "job-uuid"
}
```

### 10.3 其他调度端点

- `PUT /api/schedules/{job_id}` - 更新调度任务
- `DELETE /api/schedules/{job_id}` - 删除调度任务
- `POST /api/schedules/{job_id}/toggle` - 切换启用状态
- `POST /api/schedules/{job_id}/run` - 立即运行
- `GET /api/schedules/{job_id}/history` - 获取运行历史

**响应格式**: 均为 `{"success": true, ...}`

---

## 11. 统计 API（同步）

### 11.1 GET /api/stats

**响应**:
```json
{
  "success": true,
  "stats": {
    "total_articles": 150,
    "total_sources": 3,
    "articles_today": 15,
    "sources_enabled": 2
  }
}
```

---

## 12. 错误响应规格

### 12.1 标准错误格式

```json
{
  "success": false,
  "error": "ErrorMessage",
  "message": "具体错误描述"
}
```

**注意**: 异步任务的错误通过 `GET /api/tasks/{task_id}` 获取（status="error"）

### 12.2 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功（包括 `{"success": false}` 的业务错误） |
| 400 | 参数验证失败（请求格式错误） |
| 404 | 资源不存在（文章、RSS 源等） |
| 500 | 服务器内部错误 |

---

## 13. WebSocket 规格

### 13.1 任务进度推送

```
ws://host:8000/ws/tasks/{task_id}
```

**消息格式**:
```json
{
  "type": "task_update",
  "task_id": "uuid",
  "status": "running",
  "progress": 75,
  "message": "正在处理第 15 篇..."
}
```

**事件类型**:
- `task_update` - 任务状态更新（进度、消息）
- `article_added` - 文章已添加（实时更新文章列表）

---

## 14. 前端交互规格

### 14.1 异步任务处理流程

```javascript
// 1. 发起任务
const resp = await fetch('/api/collect/all', {method: 'POST', body: formData});
const data = await resp.json();
if (data.task_id) {
  showToast('采集任务已启动', 'info');
  pollTask(data.task_id, 'collect_all');
}

// 2. 轮询任务状态
async function pollTask(taskId, action) {
  const resp = await fetch(`/api/tasks/${taskId}`);
  const task = await resp.json();
  
  if (task.status === 'running') {
    updateProgress(task.progress, task.message);
    setTimeout(() => pollTask(taskId, action), 1000);
  } else if (task.status === 'done') {
    showToast('任务完成', 'success');
    handleResult(task.result);
  } else if (task.status === 'error') {
    showToast(`任务失败: ${task.message}`, 'error');
  }
}
```

### 14.2 Toast 通知

```javascript
// 成功
showToast('采集完成，共 15 篇', 'success');

// 错误
showToast('采集失败: 网络超时', 'error');

// 信息
showToast('正在处理...', 'info');
```

### 14.3 按钮状态管理

```
点击 → 显示 spinner → 禁用按钮 → 任务完成后恢复
```

---

## 15. 版本兼容性

| 版本 | 兼容性 |
|------|--------|
| v0.1.0 | 当前版本，API 可能变更 |
| v1.0.0 | 计划稳定版，保证向后兼容 |

**变更日志**:
- v1.1.0 (2026-05-27): 更新为异步任务模式，修复与实际代码不一致的问题
- v1.0.0 (2026-05-25): 初始版本（同步响应格式，与实际不符）

---

## 16. 待验证项目

- [x] POST `/api/collect/all` 存在 ✅
- [x] POST `/api/rewrite` 存在 ✅
- [x] 异步任务模式已实现 ✅
- [ ] WebSocket 实时推送是否已实现？
- [ ] 错误处理是否统一？

---

## 17. 下一步行动

1. **验证 WebSocket 实现** - 检查 `web/static/*.js` 中的 WebSocket 客户端代码
2. **补充错误处理测试** - 测试各种失败场景（网络错误、API 错误等）
3. **更新前端代码** - 确保前端正确处理异步任务模式
4. **补充 API 集成测试** - 使用 `requests` 或 `httpx` 测试完整流程
