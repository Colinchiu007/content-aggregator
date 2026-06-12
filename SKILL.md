---
name: content-aggregator
description: 内容聚合与改写平台。采集互联网内容（RSS/URL/爬虫），通过 AI 进行深度改写（SUMMARIZE/STYLE_TRANSFER/PARAPHRASE/REWRITE/EXPAND/SHORT_VIDEO 六种策略），支持多格式导出（Markdown/HTML/JSON/TXT/小红书），集成敏感词过滤和 SimHash 去重。当用户需要：采集网页内容、批量改写文章、AI 重写文案、内容去重、导出为多格式时使用此技能。
---

# Content Aggregator

内容聚合与改写平台。将互联网优质内容转化为标准化内容资产，赋能内容创作者高效运营多平台。

## OpenClaw 工具

本技能提供以下 OpenClaw 工具（`tools/` 目录）：

| 工具 | 功能 | 调用方式 |
|------|------|----------|
| `tools/collect.py` | 采集单个 URL 内容 | `python -m tools.collect <url>` |
| `tools/rewrite.py` | AI 改写文章内容 | `python -m tools.rewrite <title> <file>` |
| `tools/export.py` | 导出内容为多种格式 | `python -m tools.export <title> <file> [formats]` |
| `tools/seo.py` | SEO 优化（关键词/描述/标签） | `python -m tools.seo <title> <file>` |

### 工具详情

#### collect_content(url, config_path=None)
采集指定 URL 的内容，返回标题和正文。

**参数：**
- `url`: 要采集的 URL
- `config_path`: 配置文件路径（可选）

**返回：**
```json
{
  "success": true,
  "content": {
    "id": "...",
    "title": "文章标题",
    "body": "文章正文",
    "source_url": "..."
  },
  "error": null
}
```

#### rewrite_content(title, content, source_url="", strategy="REWRITE", config_path=None)
使用 LLM 改写文章内容，支持 6 种策略。

**参数：**
- `title`: 文章标题
- `content`: 文章正文
- `source_url`: 来源 URL（可选）
- `strategy`: 改写策略，可选 SUMMARIZE|STYLE_TRANSFER|PARAPHRASE|REWRITE|EXPAND|SHORT_VIDEO
- `config_path`: 配置文件路径（可选）

**返回：**
```json
{
  "success": true,
  "rewritten": {
    "title": "改写后的标题",
    "content": "改写后的正文",
    "strategy": "REWRITE"
  },
  "error": null
}
```

#### export_content(title, content, rewritten_title=None, rewritten_content=None, formats=None, output_dir=None, config_path=None)
将内容导出为指定格式。

**参数：**
- `title`: 原标题
- `content`: 原正文
- `rewritten_title`: 改写后标题（可选）
- `rewritten_content`: 改写后正文（可选）
- `formats`: 导出格式列表，可选 markdown|html|json|txt|xhs
- `output_dir`: 输出目录（可选）
- `config_path`: 配置文件路径（可选）

**返回：**
```json
{
  "success": true,
  "files": ["/path/to/output.md"],
  "error": null
}
```

#### seo_optimize(title, content, source_url="", config_path=None)
对内容进行 SEO 优化，生成关键词、描述和标签。

**参数：**
- `title`: 文章标题
- `content`: 文章正文
- `source_url`: 来源 URL（可选）
- `config_path`: 配置文件路径（可选）

**返回：**
```json
{
  "success": true,
  "seo": {
    "keywords": ["关键词1", "关键词2"],
    "description": "SEO 描述",
    "title": "SEO 标题",
    "tags": ["标签1", "标签2"]
  },
  "duration": 6.41,
  "error": null
}
```

---

## 使用方式

### Web UI（推荐，图形界面）
```bash
cd C:\Users\邱领\.qclaw\workspace-agent-904355f2\content-aggregator
py scripts/web.py
```
启动后访问 http://localhost:8080，提供仪表盘、文章列表/详情、数据源管理、手动改写、任务进度（WebSocket）等图形界面。

### CLI（适合自动化）
```bash
cd C:\Users\邱领\.qclaw\workspace-agent-904355f2\content-aggregator
py scripts/run.py --url "https://feeds.feedburner.com/ruanyifeng" --format markdown
py scripts/run.py --url "..." --strategy SHORT_VIDEO --format xhs
py scripts/run.py --file urls.txt --no-rewrite --format html
```

完整参数：
- `--url <url>` 单条 URL
- `--file <path>` 批量文件（每行一个 URL）
- `--format <markdown|html|json|txt|xhs>` 导出格式（可多次指定）
- `--strategy <SUMMARIZE|STYLE_TRANSFER|PARAPHRASE|REWRITE|EXPAND|SHORT_VIDEO>` 改写策略，默认 REWRITE
- `--no-rewrite` 仅采集，不改写
- `--seo` 启用 SEO 优化
- `--help` 查看完整参数

## 核心功能

| 功能 | 说明 |
|------|------|
| RSS 采集 | feedparser 解析，支持代理 |
| 自定义 URL 采集 | 任意网页内容抓取 |
| AI 改写 | 6 种策略，DeepSeek/OpenAI/Qwen |
| 内容过滤 | DFA 敏感词 + SimHash 去重 |
| 多格式导出 | Markdown/HTML/JSON/TXT/小红书 |
| SEO 优化 | 关键词提取、自动内链、描述生成 |
| Web UI | 图形化管理界面（端口 8080）|
| 定时调度 | Cron 表达式，周期性自动采集 |

## 配置

配置文件：`config/config.yaml`

```yaml
llm:
  provider: "deepseek"        # deepseek / openai / qwen
  api_key: "${LLM_API_KEY}"  # 或直接填入 "sk-xxx"
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"

proxy:
  enabled: true
  url: "http://127.0.0.1:12334"  # Hiddify 代理

export:
  output_dir: "./output/exports"
```

## 项目路径

```
C:\Users\邱领\.qclaw\workspace-agent-904355f2\content-aggregator\
```

- 入口脚本：`scripts/run.py`、`scripts/web.py`
- 配置目录：`config/`
- 导出输出：`output/exports/`
- 功能规格：`SPEC.md`
