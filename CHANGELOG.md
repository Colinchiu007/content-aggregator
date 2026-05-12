# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Content Filtering Module** (`processors/filter/`)
  - `sensitive.py` - 敏感词过滤器（DFA 算法，支持自定义词库、白名单、拼音检测）
  - `dedup.py` - 相似度去重（SimHash + MinHash 双重算法）
- **Configurable Rewrite Prompts** - 改写提示词可配置化
  - 支持从 `config.yaml` 的 `rewrite.prompts` 覆盖任意策略提示词
  - `RewriteConfig.custom_prompt` 支持代码级最高优先级自定义
  - 三级优先级：`custom_prompt` > `config prompts` > 内置默认值
- **SHORT_VIDEO Strategy** - 短视频文案仿写策略
  - 内置默认提示词：40-50% 相似度控制，四步仿写流程，禁用 emoji 输出
- **Environment Variable Expansion** - 环境变量展开
  - `config/loader.py` 支持 `${VAR}` 和 `${VAR:-default}` 语法
- **SQLite Storage** - 结构化数据持久化（`storage/database.py`）
- **Xiaohongshu Exporter** - 小红书格式导出器

### Fixed
- `config/loader.py`：正则 `[^}:]` 改为 `[^}]`，支持含冒号的变量名（如 `DATABASE_URL`）
- `pipeline.py`：补全 `SourceConfig`、`RewriteConfig`、`RewriteStrategy`、`RSSSource` 导入

---

## [0.1.0] 2026-05-11 - Phase 1 MVP

### Added
- **RSS Collector** - `sources/rss.py`
  - 支持 httpx 异步采集，自动跟随重定向
  - 支持代理配置（`proxy=` 参数传入 `AsyncClient`）
  - 自动解析标题、内容、作者、发布日期、标签
  - `test()` 方法支持数据源健康检查
- **AI Rewrite Processor** - `processors/rewrite.py`
  - 5 种改写策略：SUMMARIZE / STYLE_TRANSFER / PARAPHRASE / REWRITE / EXPAND
  - DeepSeek / OpenAI / Qwen API 兼容（OpenAI 兼容格式）
  - 并发控制（`asyncio.Semaphore`，默认 3 并发）
  - 自动重试（429 限流指数退避）
  - Token 用量跟踪（prompt / completion / total）
- **Content Formatter** - `processors/formatter.py`
  - `markdown_to_wechat_html()`：微信公众号内联样式转换
  - `ContentFormatter` 类：统一格式化入口
- **Exporters** - `exporters/`
  - Markdown：YAML frontmatter + 正文
  - HTML：微信内联样式，可直接粘贴到公众号
  - JSON：完整结构化字段
  - TXT：纯文本
- **CLI Tool** - `scripts/run.py`
  - `--url` / `--file`：单条或批量处理
  - `--format`：多格式导出
  - `--strategy`：指定改写策略
  - `--no-rewrite` / `--limit` / `--quiet` / `--verbose`
- **Data Models** - `models.py`
  - `Content`：采集原始数据模型
  - `Article`：改写后输出模型
  - `RewriteResult` / `CollectionResult` / `ExportResult`
- **Project Structure**
  - `config/config.yaml` + `config/config.example.yaml`
  - `requirements.txt` + `pyproject.toml`
  - `SPEC.md` - 详细功能规格说明

---

## [0.0.0] 2026-05-10 - 项目初始化

### Added
- 从 `wechat-mp-automation` 衍生，定位调整为通用内容聚合平台
- 剥离微信公众号发布相关代码（账号权限限制，暂缓）
- 创建完整项目结构
