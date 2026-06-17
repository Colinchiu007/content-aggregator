# 定时调度器详细规格

> 版本: 1.0.0  
> 最后更新: 2026-05-28  
> 状态: 基于现有代码反向工程

---

## 1. 概述

### 1.1 架构概览

Content-Aggregator 包含**两个独立的调度器实现**，面向不同运行模式：

```
┌──────────────────────────────────────────────────────────────┐
│                   调度器架构                                  │
├──────────────────────────┬───────────────────────────────────┤
│ ContentScheduler          │ BackgroundScheduler               │
│ (src/content_aggregator/  │ (web/server_scheduler.py)        │
│  scheduler.py)            │                                   │
├──────────────────────────┼───────────────────────────────────┤
│ 运行模式：CLI run.py       │ 运行模式：Web UI server.py         │
│ 生命周期：命令结束时停止    │ 生命周期：随 Web 服务器运行        │
│ 配置来源：config.yaml      │ 配置来源：Web API 动态管理         │
│ 持久化：配置文件            │ 持久化：config.yaml（CRUD API）    │
│ 关键词过滤：无             │ 关键词过滤：有                     │
│ 执行历史：内存（最近100条） │ 执行历史：内存（每任务最近50条）     │
└──────────────────────────┴───────────────────────────────────┘
```

### 1.2 共同特性

| 特性 | ContentScheduler | BackgroundScheduler |
|------|-----------------|---------------------|
| 调度类型 | interval / cron / once | interval / cron / once |
| Cron 格式 | 分 时 日 月 周 | 分 时 日 月 周 |
| 重试机制 | ✅（默认3次，间隔60s） | ✅ |
| 执行历史 | ✅（最近100条） | ✅（每任务50条） |
| WebSocket 通知 | ❌ | ✅（执行完成 toast） |
| TaskManager 集成 | ❌ | ✅ |

---

## 2. 调度类型

### 2.1 三种类型

| 类型 | 标识符 | 触发条件 |
|------|--------|----------|
| 间隔循环 | `interval` | 每隔固定秒数执行一次，首次立即执行 |
| Cron 定时 | `cron` | 符合 Cron 表达式时执行 |
| 一次性 | `once` | 在指定时间执行一次后结束 |

### 2.2 Cron 表达式格式

**格式**：`分 时 日 月 周`

```
0 9 * * *       每天 09:00
*/15 * * * *    每 15 分钟
0 9,18 * * 1-5  工作日 09:00 和 18:00
30 14 * * 0,6   周末 14:30
0 */2 * * *     每 2 小时
```

**字段范围**：

| 字段 | 允许值 | 特殊字符 |
|------|--------|----------|
| 分 | 0-59 | `*`, `*/n`, `,`, `-` |
| 时 | 0-23 | 同上 |
| 日 | 1-31 | 同上 |
| 月 | 1-12 | 同上 |
| 周 | 0-6 (0=周日) | 同上 |

**特殊字符支持**：
- `*` — 任意值
- `*/n` — 每隔 n
- `n,m,o` — 多值
- `n-m` — 范围

**⚠️ 周字段映射差异**：
- Python `weekday()`：0=周一，6=周日
- Cron 表达式：0=周日，6=周六
- 两个调度器均有正确转换逻辑

### 2.3 下次执行时间计算

```python
# interval：当前时间 + interval_hours
next_dt = datetime.datetime.now() + datetime.timedelta(hours=interval_hours)

# cron：遍历式搜索（最多搜索 1 年 × 1 分钟粒度）
candidate = now + timedelta(minutes=1)
for _ in range(366 * 24 * 60):
    if _matches_cron(candidate, minute, hour, day, month, weekday):
        return candidate
    candidate += timedelta(minutes=1)
```

---

## 3. ContentScheduler（CLI 调度器）

**位置**：`src/content_aggregator/scheduler.py`

### 3.1 接口

```python
class ContentScheduler:
    def __init__(self, config: dict) -> None
    def add_interval_task(name, interval_seconds, callback, enabled, max_retries) -> None
    def add_cron_task(name, cron_expression, callback, enabled, max_retries) -> None
    def add_once_task(name, run_at, callback, enabled) -> None
    def load_from_config(config: dict) -> None  # 从 config.yaml 加载
    async def start() -> None
    async def stop() -> None
    def get_task_status() -> list[dict]
    def get_execution_history(task_name, limit) -> list[dict]
    @property running -> bool
    @property task_count -> int
    @property enabled_task_count -> int
```

### 3.2 配置格式（config.yaml）

```yaml
scheduler:
  enabled: true
  jobs:
    - name: "早间新闻"
      type: "interval"
      interval_hours: 6
      rewrite: true
      translate: ""
      seo: false
      formats: ["markdown"]
      limit_per_source: 20
      enabled: true

    - name: "工作日推送"
      type: "cron"
      cron: "0 8 * * 1-5"
      rewrite: true
      enabled: true
```

### 3.3 执行流程

```
load_from_config()
    │
    ▼
为每个 job 创建 callback（内部启动 ContentPipeline）
    │
    ▼
start()
    │
    ├── interval: 立即执行一次 → 循环 sleep → 执行
    ├── cron:     循环计算下次时间 → sleep → 执行
    └── once:    sleep 到点 → 执行一次 → 退出
```

### 3.4 任务回调（callback）

```python
async def callback(cfg=config, jc=job):
    async with ContentPipeline(cfg) as pipeline:
        result = await pipeline.process_all_sources(
            rewrite=jc.get("rewrite", True),
            translate=jc.get("translate", False),
            target_language=jc.get("target_language"),
            seo=jc.get("seo", False),
            formats=jc.get("formats", ["markdown"]),
            limit_per_source=jc.get("limit_per_source", 20),
        )
```

⚠️ **闭包陷阱**：`callback` 使用默认参数 `cfg=config, jc=job` 捕获循环变量，避免闭包中变量后续被覆盖。

### 3.5 重试机制

```python
for attempt in range(max_retries):  # 默认 3 次
    try:
        await callback()
        return
    except Exception as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_interval)  # 默认 60s
```

---

## 4. BackgroundScheduler（Web UI 调度器）

**位置**：`web/server_scheduler.py`

### 4.1 接口

```python
class BackgroundScheduler:
    def __init__(self, config, article_store, task_manager, broadcast_fn) -> None

    # 生命周期
    async def start() -> None
    async def stop() -> None

    # 加载/保存（与 config.yaml 同步）
    def load_jobs(jobs: list[dict]) -> None
    def save_jobs() -> list[dict]

    # CRUD
    def create_job(data: dict) -> dict
    def get_job(job_id: str) -> dict | None
    def update_job(job_id: str, data: dict) -> dict | None
    def delete_job(job_id: str) -> bool
    def toggle_job(job_id: str) -> dict | None

    # 手动触发
    async def run_now(job_id: str) -> dict | None

    # 查询
    def list_jobs() -> list[dict]
    def get_history(job_id: str, limit: int) -> list[dict]
```

### 4.2 Job 数据结构

**存储格式**（config.yaml 持久化）：

```python
{
    "id": "uuid-string",
    "name": "早间新闻",
    "type": "interval",           # interval | cron | once
    "interval_hours": 6,
    "cron": "0 9 * * *",          # cron 类型使用
    "sources": [],                 # 空=全源，非空=指定数据源
    "keywords": ["AI", "技术"],
    "rewrite": true,
    "translate": "",               # 空=不翻译，非空=目标语言
    "enabled": true,
}
```

**运行时状态**（内存，不持久化）：

```python
{
    # 存储字段（见上）+ 以下运行时字段：
    "last_run": "2026-05-28T08:00:00",   # 上次执行时间（ISO）
    "next_run": "2026-05-28T14:00:00",   # 下次执行时间（ISO）
    "status": "idle",                     # idle | running | error
    "last_error": None,                   # 最近一次错误信息
}
```

### 4.3 执行流程

```
用户通过 API 创建/更新 job
    │
    ▼
save_jobs() → _save_schedules_to_config() → config.yaml
    │
    ▼
bg_scheduler._job_loop(job) → interval/cron/once 分支
    │
    ▼
_execute_job()
    │
    ├── 创建 TaskManager 任务
    ├── keywords 过滤（标题+正文包含关键词）
    ├── sources 非空 → _collect_source()（仅 RSS）
    │                 └── 复用 ContentPipeline.process_url()
    └── sources 为空 → _collect_all()
                        └── 复用 ContentPipeline.process_all_sources()
    │
    ▼
执行结果写入 _history[job_id]（最近 50 条）
    │
    ▼
WebSocket 广播 toast 通知
```

### 4.4 Web API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/schedules` | 列出所有任务 |
| POST | `/api/schedules` | 创建新任务 |
| PUT | `/api/schedules/{job_id}` | 更新任务 |
| DELETE | `/api/schedules/{job_id}` | 删除任务 |
| POST | `/api/schedules/{job_id}/toggle` | 启用/禁用 |
| POST | `/api/schedules/{job_id}/run` | 立即执行一次 |
| GET | `/api/schedules/{job_id}/history` | 执行历史 |

### 4.5 执行历史记录

```python
record = {
    "id": str(uuid.uuid4()),
    "job_id": job_id,
    "job_name": job["name"],
    "started_at": started_at.isoformat(),
    "finished_at": finished_at.isoformat(),
    "duration_sec": 3.2,
    "success": True,
    "error": None,
    "articles_count": 5,
    "is_manual": False,  # True=手动触发
}
```

---

## 5. 关键词过滤

仅 `BackgroundScheduler` 支持，在 `_execute_job()` 中实现：

```python
# 构建关键词列表（小写）
kw_lower = [k.lower().strip() for k in keywords if k.strip()]

# 对每篇文章过滤
title = (article.title or "").lower()
content = (article.content or "").lower()
if not any(k in title or k in content for k in kw_lower):
    continue  # 跳过不匹配的文章
```

⚠️ 关键词为**包含匹配**（OR 逻辑），任意一个关键词命中即保留。

---

## 6. 关键设计决策

### 6.1 两个调度器并存的原因

- **ContentScheduler**：早期实现，面向 CLI 用户，适合无 Web 界面的服务器部署
- **BackgroundScheduler**：为 Web UI 深度定制，支持 CRUD API、关键词过滤、WebSocket 通知

两者未来可能**合并统一**，共享核心调度逻辑，BackgroundScheduler 继承 ContentScheduler。

### 6.2 关键词过滤仅在 BackgroundScheduler 中

ContentScheduler 调用 `process_all_sources()` 时无关键词过滤参数，关键词过滤通过文章级别的 post-filter 实现（`_execute_job` 中 `continue` 跳过不匹配文章）。

### 6.3 Cron 解析：遍历 vs 解析器

两者均使用**暴力遍历**（每分钟向前搜索），最多搜索 1 年。性能可接受（最坏 ~53 万次迭代），但存在优化空间：
- 使用 `croniter` 库（第三方）替代自实现
- 缓存下次时间，避免重复计算

---

## 7. 已知限制

| # | 限制 | 优先级 |
|---|------|--------|
| 1 | `_collect_source()` 仅支持 RSS 源，非 RSS 回退到警告日志 | 中 |
| 2 | `ContentScheduler` 无法指定数据源采集 | 低 |
| 3 | 两个调度器代码重复，缺乏继承结构 | 低 |
| 4 | Cron 解析为遍历实现，无外部库依赖 | 低 |
| 5 | 执行历史内存态，进程重启丢失 | 低 |
| 6 | `BackgroundScheduler._collect_source()` 在 `async with ContentPipeline` 块内处理文章 —— 正确，但内部状态清理时机需注意 | 中 |
