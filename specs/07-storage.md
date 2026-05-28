# 存储层详细规格

> 版本: 1.0.0  
> 最后更新: 2026-05-28  
> 状态: 基于现有代码反向工程

---

## 1. 概述

### 1.1 存储架构

Content-Aggregator 采用**轻量级多层级存储**架构，无外部数据库依赖。按数据生命周期分为三层：

```
┌─────────────────────────────────────────────────────┐
│                   存储层架构                          │
├──────────┬──────────┬──────────┬────────────────────┤
│  Layer 1 │  Layer 2 │  Layer 3 │      Layer 4       │
│ 内存运行时 │ JSON 缓存 │ 文件导出  │   去重索引(内存)   │
│ Pipeline  │ArticleStore│Exporter │   DedupFilter     │
│ 状态/任务  │ Web持久化  │ 格式输出  │   SensitiveFilter │
└──────────┴──────────┴──────────┴────────────────────┘
```

| 层级 | 组件 | 持久化 | 用途 |
|------|------|--------|------|
| L1 内存 | `TaskManager`, `DedupFilter`, `SensitiveFilter` | ❌ | 运行时状态、去重索引 |
| L2 JSON | `ArticleStore` (Web UI) | ✅ JSON 文件 | 文章缓存、Web 展示 |
| L3 文件 | `Exporter` | ✅ 磁盘文件 | 多格式导出输出 |
| L4 配置 | `config.yaml` | ✅ YAML 文件 | 全局配置持久化 |

### 1.2 设计决策

- **无数据库**：面向个人使用场景（百级文章），JSON 文件 + 目录遍历比 SQLite 更轻量
- **去重内存态**：`DedupFilter` 的 hash 索引和内容缓存仅在 Pipeline 运行期间存在，进程退出即丢失
- **Web 独立存储**：`ArticleStore` 在 Web UI 中独立管理，不与 Pipeline 的内存 Article 对象共享

---

## 2. Layer 1：内存运行时存储

### 2.1 TaskManager

**位置**：`web/server.py`（内联类）

管理后台采集任务的运行状态，纯内存字典。

```python
class TaskManager:
    tasks: dict[str, dict]
```

**Task 数据结构**：

```python
{
    "id": "task_1716789123_4567",    # 格式: task_{timestamp}_{instance_id}
    "type": "collect_all",            # 任务类型
    "description": "全源采集",         # 描述
    "status": "pending",              # pending | running | done | error
    "progress": 0,                    # 0-100
    "message": "",                    # 状态消息
    "result": None,                   # 任务结果（dict 或 None）
    "created_at": "2026-05-28T00:00:00",
    "started_at": None,               # status=running 时记录
    "finished_at": None,              # status=done/error 时记录
}
```

**生命周期**：
- 创建：`create(task_type, description)` → 返回 `task_id`
- 更新：`update(task_id, status, progress, message, result)`
- 查询：`get(task_id)`, `get_all()`
- **不持久化**：进程重启后任务历史丢失

### 2.2 DedupFilter 去重索引

**位置**：`src/content_aggregator/processors/filter/dedup.py`

```python
class DedupFilter:
    _seen_hashes: set[str]        # MD5 hash 集合（精确去重）
    _seen_contents: list[dict]     # 最近 100 条内容记录（模糊去重）
```

**去重算法**：

| 算法 | 方法 | 用途 |
|------|------|------|
| 精确去重 | MD5 hash（标准化后） | 完全相同内容检测 |
| 模糊去重 | Jaccard + Levenshtein（字符集） | 相似内容检测，阈值 0.8 |
| 文本标准化 | 去空白 + 小写 + strip | 统一比较基准 |

**内存管理**：
- `_seen_contents` 保留最近 **100 条**，超出自动裁剪
- `_seen_hashes` 无上限（但受 Pipeline 单次运行的文章量约束）
- `reset()` 方法清空所有状态

**⚠️ 关键限制**：
- 去重索引仅在**单次 Pipeline 运行**内有效
- 进程重启后去重历史丢失，同一文章可能被重复采集
- Web UI 的 `ArticleStore` 有独立去重（按 `title + source_url`），但 Pipeline 不感知

### 2.3 SensitiveFilter 敏感词索引

**位置**：`src/content_aggregator/processors/filter/sensitive.py`

- 加载敏感词列表到内存 `set`
- 支持 `strict_mode`（严格模式：命中任意关键词即拦截）
- 敏感词列表来源：配置文件或内置默认词库

---

## 3. Layer 2：JSON 文件持久化（ArticleStore）

**位置**：`web/server.py`（内联类）

### 3.1 接口

```python
class ArticleStore:
    def __init__(self, data_dir: str = "./data") -> None
    def add(article: dict) -> bool           # 添加（去重）
    def add_batch(articles: list[dict]) -> int  # 批量添加
    def get_by_id(article_id: str) -> dict | None
    def get_all(page, per_page, source) -> dict  # 分页
    def delete(article_id: str) -> bool
    def clear() -> None
    def get_sources() -> list[dict]          # 来源统计
    def save() -> None                       # 手动持久化
```

### 3.2 存储文件

| 文件 | 路径 | 格式 |
|------|------|------|
| 文章缓存 | `{data_dir}/articles_cache.json` | JSON 数组 |

### 3.3 数据结构

每篇文章存储为：

```json
{
    "id": "uuid-string",
    "title": "文章标题",
    "content": "正文内容（改写后）",
    "source": "rss",
    "source_url": "https://...",
    "author": "作者",
    "summary": "摘要",
    "tags": ["tag1"],
    "word_count": 3000,
    "collected_at": "2026-05-28T00:00:00",
    "metadata": {
        "rewritten": true,
        "rewrite_strategy": "REWRITE",
        "original_content": "原始正文",
        "original_title": "原始标题"
    }
}
```

### 3.4 去重策略

```python
def _is_duplicate(self, article: dict) -> bool:
    # 按 title + source_url 判断
    title = article.get("title", "").strip()
    source_url = article.get("source_url", "").strip()
```

- 两个条件**同时匹配**才视为重复
- 标题为空时不参与去重
- 新文章插入到列表**头部**（最新在前）

### 3.5 持久化时机

| 操作 | 自动保存 |
|------|----------|
| `add()` | ✅ |
| `add_batch()` | ✅ |
| `delete()` | ✅ |
| `clear()` | ✅ |
| 字段修改（如改写后更新） | ⚠️ 需手动调用 `save()` |

### 3.6 分页

```python
def get_all(self, page: int = 1, per_page: int = 20, source: str | None = None) -> dict
```

返回：

```python
{
    "items": [...],      # 当前页文章
    "total": 100,        # 总数
    "page": 1,           # 当前页
    "per_page": 20,      # 每页数量
    "pages": 5,          # 总页数
}
```

---

## 4. Layer 3：文件导出（Exporter）

**位置**：`src/content_aggregator/exporters/__init__.py`

### 4.1 接口

```python
class Exporter:
    def __init__(self, output_dir: str = "./output/exports") -> None
    def export(article: Article, format_type: str) -> str  # 导出单个
    def export_batch(articles, format_types) -> list[str]  # 批量导出
    def list_exports() -> list[dict]                       # 列出已导出文件
```

### 4.2 输出目录结构

```
{output_dir}/
├── 文章标题_safe.md       # Markdown
├── 文章标题_safe.html     # HTML
├── 文章标题_safe.json     # JSON
├── 文章标题_safe.txt      # 纯文本
├── 文章标题_safe.pdf      # PDF
└── 文章标题_safe.md       # 小红书（.md 扩展名）
```

### 4.3 文件命名规则

```python
safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
filename = f"{safe_title}.{ext}"
```

- 替换 Windows 非法字符为下划线
- 标题截断至 50 字符
- ⚠️ **同名文章覆盖**：相同标题的导出文件会被覆盖（无版本管理）

### 4.4 导出失败处理

```python
# export_batch 中捕获异常并记录日志，不中断其他文章导出
except Exception as e:
    logger.error(f"Export failed for {article.title} ({fmt}): {e}")
```

---

## 5. Layer 4：配置持久化

**位置**：`web/server.py` → `load_config()` / `save_config()`

### 5.1 配置文件

| 文件 | 路径 | 格式 |
|------|------|------|
| 主配置 | `config/config.yaml` | YAML |

### 5.2 配置保存逻辑

```python
def save_config(config: dict) -> bool:
    # 允许 Unicode、保持插入顺序、不排序 key
    yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
```

### 5.3 API Key 安全

Web API 返回配置时自动脱敏：

```python
def mask_keys(obj, keys=("api_key", "bearer_token", "session_id", "cookie", 
                         "xhs_token", "client_key")):
    # 大于 4 字符的值替换为 "***"
```

---

## 6. 数据流图

```
                    ┌──────────────┐
    RSS/URL/... ──▶│  Collector   │
                    └──────┬───────┘
                           │ Content[]
                           ▼
                    ┌──────────────┐
                    │   Filters    │ ◄── DedupFilter(内存)
                    │ 敏感词 + 去重 │     SensitiveFilter(内存)
                    └──────┬───────┘
                           │ filtered Content[]
                           ▼
                    ┌──────────────┐
                    │  Rewriter    │
                    │  AI 改写     │
                    └──────┬───────┘
                           │ RewriteResult
                           ▼
                    ┌──────────────┐
                    │  Formatter   │
                    │  格式化输出   │
                    └──────┬───────┘
                           │ Article[]
                    ┌──────┴───────┐
                    ▼              ▼
             ┌────────────┐ ┌────────────┐
             │  Exporter  │ │ArticleStore│
             │  文件导出   │ │ JSON 持久化│
             └────────────┘ └────────────┘
```

---

## 7. 已知限制与改进方向

### 7.1 当前限制

| # | 限制 | 影响 | 优先级 |
|---|------|------|--------|
| 1 | 去重索引不持久化 | 进程重启后重复采集 | 中 |
| 2 | 导出文件无版本管理 | 同名覆盖 | 低 |
| 3 | TaskManager 不持久化 | 重启后任务历史丢失 | 低 |
| 4 | JSON 全量读写 | 文章量大时性能下降 | 低 |
| 5 | ArticleStore 改写后需手动 save() | 可能丢失更新 | 中 |

### 7.2 建议改进

| # | 改进 | 说明 |
|---|------|------|
| 1 | 去重索引持久化 | 使用 SQLite 或 JSON 文件存储 hash 集合 |
| 2 | 导出文件名添加时间戳 | `标题_20260528.md` 避免覆盖 |
| 3 | Article.save() 自动化 | 在所有修改 Article 字段的操作后自动触发 |

---

## 8. 存储路径汇总

| 存储 | 默认路径 | 可配置 |
|------|----------|--------|
| 文章缓存 | `./data/articles_cache.json` | ❌ 硬编码 |
| 导出文件 | `./output/exports/` | ✅ `config.export.output_dir` |
| 配置文件 | `config/config.yaml` | ✅ 启动参数 |
| 日志 | loguru 默认（stderr） | ✅ loguru 配置 |
