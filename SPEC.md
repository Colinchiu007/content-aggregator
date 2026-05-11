# Content Aggregator - 内容聚合与改写平台

## 1. 概念与愿景

**定位**：通用内容处理中台，将互联网热文转化为标准化内容资产，供多平台发布使用。

**核心价值**：输入RSS源 → AI改写 → 多格式输出 → 赋能各类内容平台

**目标用户**：内容创作者、自媒体运营者、内容工作室

## 2. 功能范围

### 2.1 内容采集

- [x] RSS源采集（支持代理）
- [ ] 微信公众号文章采集
- [ ] 知乎专栏采集
- [ ] 自定义URL采集

### 2.2 内容处理

- [x] AI改写（DeepSeek/OpenAI/Qwen）
- [ ] 内容过滤（敏感词、去重）
- [ ] SEO优化
- [ ] 多语言翻译

### 2.3 导出格式

| 格式 | 用途 | 状态 |
|------|------|------|
| Markdown | 通用文字内容 | ✅ |
| HTML (内联样式) | 公众号直接用 | ✅ |
| JSON (结构化) | Skill间调用 | ✅ |
| TXT (纯文本) | 配音/摘要 | ✅ |
| 小红书格式 | 图文平台 | ✅ |
| PDF | 存档/分享 | 🔜 |

### 2.4 Skill封装

- [x] Python模块封装
- [ ] 标准化API接口
- [ ] 其他Skill调用示例

## 3. 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    Content Aggregator                     │
├─────────────────────────────────────────────────────────┤
│  Sources        │  Processors      │  Exporters          │
│  ───────────    │  ────────────    │  ────────────        │
│  • RSS          │  • Rewrite       │  • Markdown         │
│  • WebScraper   │  • Filter        │  • HTML             │
│  • CustomURL    │  • Formatter     │  • JSON             │
│                 │  • SEO           │  • TXT              │
│                 │                  │  • Xiaohongshu      │
├─────────────────────────────────────────────────────────┤
│  Storage          │  Workflows        │  API               │
│  ────────         │  ──────────       │  ───               │
│  • SQLite         │  • Pipeline       │  • ContentAPI      │
│  • FileCache      │  • Scheduler      │  • ExporterAPI      │
└─────────────────────────────────────────────────────────┘
```

## 4. 输出格式规范

### 4.1 JSON结构化输出

```json
{
  "id": "uuid",
  "title": "文章标题",
  "original_title": "原文标题",
  "source": "source_name",
  "source_url": "https://...",
  "author": "作者",
  "published_at": "2026-05-11T10:00:00Z",
  "content": "改写后的正文",
  "summary": "摘要",
  "tags": ["标签1", "标签2"],
  "word_count": 1234,
  "metadata": {
    "original_word_count": 2000,
    "rewrite_tokens": 500,
    "language": "zh-CN"
  }
}
```

### 4.2 Markdown输出

```markdown
---
title: 文章标题
author: 作者
source: 来源
date: 2026-05-11
tags: [标签1, 标签2]
---

正文内容...
```

### 4.3 HTML输出（微信内联样式）

见 formatter.py - 纯内联CSS，兼容微信渲染

## 5. API接口

### 5.1 Python模块调用

```python
from content_aggregator import ContentPipeline, exporters

# 采集+改写
pipeline = ContentPipeline(config)
article = await pipeline.process_url("https://example.com/rss.xml")

# 导出不同格式
markdown_content = exporters.to_markdown(article)
html_content = exporters.to_html(article)
json_content = exporters.to_json(article)
```

### 5.2 命令行

```bash
# 采集并导出
python -m content_aggregator --source rss.xml --format markdown --output ./output

# 改写现有文章
python -m content_aggregator --rewrite --input article.md --output ./output
```

## 6. 项目结构

```
content-aggregator/
├── SPEC.md
├── README.md
├── requirements.txt
├── pyproject.toml
├── config/
│   └── config.yaml
├── src/content_aggregator/
│   ├── __init__.py
│   ├── sources/
│   │   ├── __init__.py
│   │   └── rss.py
│   ├── processors/
│   │   ├── __init__.py
│   │   ├── rewrite.py
│   │   └── formatter.py
│   ├── exporters/
│   │   ├── __init__.py
│   │   ├── markdown_exporter.py
│   │   ├── html_exporter.py
│   │   ├── json_exporter.py
│   │   └── txt_exporter.py
│   ├── storage/
│   │   └── database.py
│   ├── workflows/
│   │   └── pipeline.py
│   └── api/
│       └── content_api.py
├── output/
│   └── exports/
└── tests/
```

## 7. 与原项目(wechat-mp-automation)的关系

- 原项目暂存，保留完整代码
- 复用：RSS采集、AI改写、格式化、数据库
- 不复用：微信公众号发布相关代码
- 本项目定位更通用，不绑定特定平台

## 8. TODO

### Phase 1 - MVP ✅
- [x] RSS采集
- [x] AI改写
- [x] Markdown导出
- [x] HTML导出（微信样式）
- [x] JSON导出

### Phase 2 - 完善
- [x] TXT导出
- [x] 小红书格式导出
- [x] 命令行工具完善
- [ ] 配置管理优化

### Phase 3 - 扩展
- [ ] 更多采集源
- [ ] 内容过滤
- [ ] SEO优化
- [ ] 多语言翻译

### Phase 4 - 集成
- [ ] Skill封装完善
- [ ] 其他Skill调用示例
- [ ] 视频生成接口预留

## 9. 技术栈

- Python 3.12+
- httpx (异步HTTP)
- feedparser (RSS解析)
- peewee + aiosqlite (数据库)
- Pydantic v2 (配置)
- aiohttp (可选)

## 10. 许可证

MIT