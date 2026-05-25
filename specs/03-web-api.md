# Web API 规格

> 版本: 1.0.0  
> 最后更新: 2026-05-25  
> 状态: 反向工程自现有代码

---

## 1. API 概览

### 1.1 基础信息

- **协议**: HTTP/1.1
- **数据格式**: JSON
- **编码**: UTF-8
- **端口**: 8000（默认）

### 1.2 端点清单

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/` | 仪表盘页面 |
| GET | `/articles` | 文章列表页面 |
| GET | `/sources` | 数据源页面 |
| GET | `/settings` | 配置编辑页面 |
| GET | `/compose` | 手动输入页面 |
| GET | `/tasks` | 任务列表页面 |
| GET | `/scheduler` | 调度管理页面 |
| POST | `/api/collect` | 执行采集 |
| POST | `/api/rewrite` | 执行改写 |
| POST | `/api/export` | 执行导出 |
| GET | `/api/articles` | 获取文章列表 |
| DELETE | `/api/articles/{id}` | 删除文章 |
| GET | `/api/tasks` | 获取任务列表 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 保存配置 |

---

## 2. 采集 API

### 2.1 POST /api/collect

**请求**:
```json
{
  "source_type": "rss",
  "source_url": "https://example.com/feed.xml",
  "rewrite": true,
  "limit": 20
}
```

**响应**:
```json
{
  "success": true,
  "collected_count": 15,
  "articles": [
    {
      "id": "uuid",
      "title": "标题",
      "original_title": "原标题",
      "source": "RSS源名称",
      "source_url": "原文链接",
      "content": "改写后内容...",
      "word_count": 2500,
      "published_at": "2026-05-25T10:00:00Z"
    }
  ]
}
```

**行为规格**:
```
1. 验证参数（source_type 必需）
2. 创建对应的 Collector
3. 执行采集
4. 如 rewrite=true，调用改写
5. 存储到数据库
6. 返回结果
```

### 2.2 POST /api/collect/youtube

**请求**:
```json
{
  "search_query": "AI教程",
  "order": "relevance",
  "max_results": 10,
  "rewrite": true
}
```

**响应**: 同上

---

## 3. 改写 API

### 3.1 POST /api/rewrite

**请求**:
```json
{
  "content": "原文内容...",
  "title": "原标题",
  "strategy": "rewrite",
  "custom_prompt": null,
  "target_word_count": 3000
}
```

**响应**:
```json
{
  "success": true,
  "title": "改写后标题",
  "content": "改写后内容...",
  "summary": "摘要...",
  "word_count": 2800,
  "duration": 12.5,
  "metadata": {
    "strategy": "rewrite",
    "original_length": 5000,
    "tokens_used": 3500
  }
}
```

---

## 4. 导出 API

### 4.1 POST /api/export

**请求**:
```json
{
  "article_id": "uuid",
  "formats": ["markdown", "html"]
}
```

**响应**:
```json
{
  "success": true,
  "paths": [
    "./output/exports/标题_20260525.md",
    "./output/exports/标题_20260525.html"
  ]
}
```

---

## 5. 文章管理 API

### 5.1 GET /api/articles

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

### 5.2 DELETE /api/articles/{id}

**响应**:
```json
{
  "success": true,
  "message": "已删除"
}
```

---

## 6. 任务 API

### 6.1 GET /api/tasks

**响应**:
```json
{
  "tasks": [
    {
      "id": "task-uuid",
      "type": "collect",
      "status": "running",
      "progress": 50,
      "created_at": "2026-05-25T10:00:00Z",
      "updated_at": "2026-05-25T10:01:00Z"
    }
  ]
}
```

**状态枚举**:
- `pending`: 等待中
- `running`: 执行中
- `done`: 已完成
- `error`: 失败

---

## 7. 配置 API

### 7.1 GET /api/config

**响应**:
```json
{
  "success": true,
  "config": {
    "llm": {...},
    "sources": {...},
    "export": {...}
  }
}
```

### 7.2 POST /api/config

**请求**:
```json
{
  "config": {
    "llm": {
      "provider": "deepseek",
      "api_key": "sk-xxx"
    }
  }
}
```

**响应**:
```json
{
  "success": true,
  "message": "配置已保存"
}
```

---

## 8. 错误响应规格

### 8.1 标准错误格式

```json
{
  "success": false,
  "error": "ValidationError",
  "message": "source_type 参数缺失",
  "details": {
    "field": "source_type",
    "constraint": "required"
  }
}
```

### 8.2 错误类型

| 类型 | HTTP 状态码 | 说明 |
|------|-------------|------|
| `ValidationError` | 400 | 参数验证失败 |
| `NotFoundError` | 404 | 资源不存在 |
| `AuthError` | 401 | 认证失败 |
| `RateLimitError` | 429 | 请求频率限制 |
| `InternalError` | 500 | 服务器内部错误 |

---

## 9. 请求/响应约束

### 9.1 请求约束

```
Content-Type: application/json
最大请求体: 10MB
超时: 300 秒（长时间任务）
```

### 9.2 响应约束

```
Content-Type: application/json
字符编码: UTF-8
日期格式: ISO 8601
```

---

## 10. WebSocket 规格（可选）

### 10.1 任务进度推送

```
ws://host/ws/tasks/{task_id}

消息格式:
{
  "type": "progress",
  "task_id": "uuid",
  "progress": 75,
  "message": "正在处理第 15 篇..."
}
```

---

## 11. 前端交互规格

### 11.1 Toast 通知

```javascript
// 成功
showToast('采集完成，共 15 篇', 'success');

// 错误
showToast('采集失败: 网络超时', 'error');

// 信息
showToast('正在处理...', 'info');
```

### 11.2 异步按钮状态

```
点击 → 显示 spinner → 禁用按钮 → 完成后恢复
```

---

## 12. 版本兼容性

| 版本 | 兼容性 |
|------|--------|
| v0.1.0 | 当前版本，API 可能变更 |
| v1.0.0 | 计划稳定版，保证向后兼容 |
