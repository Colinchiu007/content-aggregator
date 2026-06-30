---
name: content-aggregator-architecture
description: content-aggregator ARCHITECTURE.md — 系统架构
---

# Content Aggregator — 架构文档

> **版本**: v1.8.0 | **更新**: 2026-07-01

## 一、系统架构

```
┌──────────────────────────────────────────────────────────┐
│                       Web UI (Jinja2/Vue 3)               │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                      FastAPI API                           │
│  routers: collect / rewrite / export / articles / tasks   │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                        Services                            │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐  │
│  │Collect   │ │ Rewrite  │ │Export  │ │Publisher     │  │
│  │桥接/采集   │ │ 改写引擎  │ │ 导出器  │ │ 发布服务      │  │
│  └──────────┘ └──────────┘ └────────┘ └──────────────┘  │
│  ┌──────────┐ ┌──────────┐                                │
│  │Monitor   │ │Trend-Bridge│                               │
│  │ 竞品监控   │ │ 热榜桥接   │                               │
│  └──────────┘ └──────────┘                                │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                    Pipeline                                 │
│  Source → Collector → [Filter → Rewrite → Translate → SEO]│
│  → Export / Storage                                        │
└───────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                    Data Layer                               │
│  SQLite (主存储) + Celery (异步任务)                         │
└───────────────────────────────────────────────────────────┘
```

## 二、目录结构

```
content-aggregator/
├── api/v1/          # FastAPI routers
├── services/        # 业务服务层
├── src/             # 核心源码
│   └── content_aggregator/
│       ├── sources/collectors/  # 9 个采集器
│       ├── processors/          # 改写/过滤/翻译
│       ├── exporters/           # 6 种导出格式
│       └── storage/             # SQLite 存储
├── tasks.py         # Celery 任务
└── config.yaml      # 配置
```

## 三、数据流

**采集管道**: Configured Source → Collector → Pipeline → Export/Storage

**热榜发现**: TrendScope → bridge → collect → rewrite → store
PRDEOF
echo "9/10 content-aggregator ARCHITECTURE.md done"

# === 10. content-aggregator DESIGN.md ===
cat > /tmp/docs-batch/ca-DESIGN.md << 'DESIGNEOF'
---
name: content-aggregator-design
description: content-aggregator DESIGN.md — 设计细节
---

# Content Aggregator — 设计文档

> **版本**: v1.8.0 | **更新**: 2026-07-01

## 一、采集器设计

### 1.1 BaseCollector 接口

```python
class BaseCollector(ABC):
    async def fetch(self, config: SourceConfig) -> list[Content]: ...
    async def test(self) -> bool: ...
```

### 1.2 9 类采集器

| 采集器 | 认证方式 | 速率限制 |
|--------|---------|---------|
| RSSCollector | 无 | — |
| YouTubeCollector | API Key | 10K units/day |
| TwitterCollector | Bearer Token | 500K tweets/month |
| TikTokCollector | Session Cookie | 按 IP |
| DouyinCollector | Cookie + Client Key | 按 IP |
| XiaohongshuCollector | Cookie + Token | 按 IP |
| WechatCollector | 第三方 API | 按 API |
| SitemapCollector | 无 | — |
| APICollector | 自定义 Header | 自定义 |

## 二、改写策略设计

| 策略 | 输出长度 | LLM 温度 | System Prompt |
|------|---------|---------|-------------|
| summarize | 200-500 | 0.3 | 摘要提取 |
| style_transfer | 同原文 | 0.5 | 风格迁移 |
| paraphrase | 同原文 | 0.6 | 同义改写 |
| rewrite | 500-5000 | 0.7 | 深度改写 |
| expand | 3000+ | 0.8 | 内容扩展 |
| short_video | 口语化 | 0.7 | 短视频文案 |

三级提示词优先级：`custom_prompt` > `config.yaml prompts` > 内置默认值。

## 三、过滤设计

### SensitiveFilter
- 算法：DFA（确定性有限自动机）
- 模式：strict 拦截 / 非 strict 替换
- 自定义词库 + 白名单 + 拼音检测

### DedupFilter
- 精确去重：MD5 URL hash
- 模糊去重：SimHash + MinHash（阈值 0.8）

## 四、导出格式

| 格式 | 类名 | 特点 |
|------|------|------|
| Markdown | MarkdownExporter | YAML frontmatter |
| HTML | HTMLExporter | 微信内联样式 |
| JSON | JSONExporter | 完整结构化字段 |
| TXT | TXTExporter | 纯文本 |
| PDF | PDFExporter | reportlab |
| Excel | ExcelDataStore | 样式化表格 |

## 五、测试

62/62 测试 ALL GREEN：API 端点 / 采集器 / 改写 / 过滤 / 导出 / 发布集成。
DESIGNEOF
echo "10/10 content-aggregator DESIGN.md done"

ls -la /tmp/docs-batch/
