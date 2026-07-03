# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- **last30days 海外多源搜索采集器** — `Last30DaysCollector` 并行搜索 Reddit/HN/GitHub/Polymarket，支持 engagement 归一化 (log10)、加权 RRF 融合排序、30 天新鲜度衰减
- **last30days 桥接注册** — `collect_bridge.py` 硬依赖化，与其余 14 个 v1 采集器同步注册
- **last30days 测试覆盖** — 43 项单元测试（normalize_engagement/compute_freshness_score/rrf_score/并行采集/错误源恢复/去重/限流/评分公式验证）

- **Alembic 迁移链修复** — 三层链 `000_init → 2f5952d46af4(空桩) → 001`：`000_init` 创建基表（users/articles/publish_logs/tasks），`2f5952d46af4` 为空桩过渡，`001` 创建 monitor 表。修复 FUSE 导致的 `down_revision` 错乱问题
- **v1 采集器桥接** (`services/collect_bridge.py`) — 懒加载 12+ v1 采集器（YouTube/Twitter/WeChat/抖音/小红书等），支持单源采集与并行全源采集
- **测试覆盖扩展** — publisher orchestrator 集成测试（mock 成功+失败路径）+ collect_bridge 8 测试用例
- **ca_publish_to_wx Celery 任务** — 新增 `ca_publish_to_wx` 任务调用 `_execute_platform_publish` 通过 orchestrator API 转发发布请求

### Fixed
- **全量回归验证** — 62/62 测试 ALL GREEN（证明所有模块接口契约一致）
- **FUSE git 损坏恢复流程** — index 损坏后通过 /tmp 克隆提交再推送的完整流程已验证



### Fixed
- **Model import sync** — `Task` model added to `models/__init__.py` and `alembic/env.py` imports, ensuring all 6 ORM tables (users, articles, publish_logs, tasks, monitor_sources, monitor_articles) are registered in Alembic metadata
- **Test infrastructure validated** — Full regression 60/60 tests passing (up from 52 after Task model import fix)

- **热榜发现模块（F-13 集成路线）** — TrendScope → content-aggregator 热榜集成
  - `GET /api/v1/trending/platforms` — 获取热门平台列表（代理 TrendScope）
  - `GET /api/v1/trending` — 聚合热榜数据（12 平台，代理 TrendScope）
  - `GET /api/v1/trending/{platform}` — 指定平台热榜数据
  - `POST /api/v1/trending/rewrite` — 一键改写（采集原文→创建文章→跳转改写页）
  - 前端热榜发现页面：平台 tabs + 排名 + 热度值 + 一键改写按钮
  - 侧边栏「热榜发现」导航入口
  - 配置 `TRENDSCOPE_API_URL` 连接 TrendScope 服务

## [Unreleased]

### Added
- **竞品监控（F-12）** — 支持用户添加竞品账号，定期采集最新文章
  - `MonitorSource` / `MonitorArticle` 数据模型 + Alembic 迁移
  - `GET /api/v1/monitors` — 监控源 CRUD（分页 + 搜索 + 类型筛选）
  - `GET /api/v1/monitor-articles` — 监控文章列表（按源筛选，按采集时间倒序）
  - `POST /api/v1/monitor-articles/{id}/read` — 标记已读
  - `POST /api/v1/monitor-articles/{id}/rewrite` — 一键改写（异步 Celery 任务）
  - `ca_collect_monitors` — Celery 定时采集任务（占位实现）
  - 前端 MonitorView.vue — 监控源管理 + 文章列表双 Tab 页面
  - 前端 /monitor 路由 + 侧边栏「竞品监控」入口（TrendCharts 图标）
  - PRD 同步：F-12 状态更新为 ✅ 已完成


### Added
- **PRD 同步** — 更新 v1.5.0~v1.8.0 功能状态，5 项 v1.5.0 功能从 🚧 → ✅
- **YouTube 采集排序选项** — 后端 API + 前端 SettingsView 下拉框配置
- **封面管理模块（v2 实现）** — cover_router + 前端 SettingsView 集成
- **前端重设计「信息实验室」** — 品牌升级 + 布局重构 + 暗色模式
  - 品牌从 HotRewrite 升级为「信息实验室」
  - 新增深色侧边栏导航（可折叠），顶部导航精简为用户菜单
  - 全新设计系统 CSS 变量（`--il-*`），支持明暗主题切换
  - 所有页面统一空状态、加载骨架屏、页面过渡动画
  - 响应式布局（平板端自适应）
  - 首页快捷操作卡片 + 全新 Hero 区域

  - `POST /covers/generate` — DALL-E 3 AI 封面生成（多 Provider 扩展架构）
  - `GET /covers` — 已生成封面列表
  - `POST /covers/default` — 上传默认封面
  - `GET /covers/default` — 获取默认封面信息
  - `DELETE /covers/default` — 删除默认封面
  - 前端设置页封面管理区：默认封面上传/预览/删除、AI 生成、封面画廊

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
- **Multi-language Translation** (`processors/translator.py`)
  - 支持 10 种语言：EN/JA/KO/FR/DE/ES/PT/RU/AR/VI
  - 每种语言内置专属翻译提示词（非通用提示词）
  - 支持语气风格（formal/casual/academic）和格式保留
  - `TranslatorProcessor` 与 `RewriteProcessor` 共用 LLM 配置
- **Scheduler** (`scheduler.py`)
  - 三种调度类型：INTERVAL（固定间隔）/ CRON（Cron 表达式）/ ONCE（一次性）
  - 完整 Cron 解析器（*/n、范围、多值、步进）
  - 自动重试机制（默认 3 次）+ 执行历史记录（最近 100 条）
- **PDF Exporter** (`exporters/pdf_exporter.py`)
  - Markdown 内容解析（标题/列表/引用/代码块）
  - 中文字体支持（可配置字体路径）
  - 微信公众号 HTML 直接转换
  - 可配置页面大小（A4/Letter/Legal）、字体、边距
  - 需安装：`pip install reportlab`

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

---

## [Unreleased] 2026-06-26

### Fixed
- **Publisher service** (`services/publisher.py`): Now dispatches Celery tasks (`ca_publish_to_wx.delay`) for each platform after creating PublishLog records, instead of only creating logs without async execution
- **Celery task signature** (`tasks.py`): Fixed `ca_publish_to_wx` — now accepts `(article_id, platform)` matching the caller in `create_publish_tasks`. Task calls `_execute_platform_publish` to update PublishLog status
- **Duplicate modules**: Removed `services/collector.py` and `services/rewriter.py`. Updated all imports in `api/v1/collector.py`, `api/v1/rewriter.py`, `services/__init__.py`, and `tasks.py` to use the standalone `services/collect.py` and `services/rewrite.py`
- **Auth endpoint** (`api/v1/auth.py`): Fixed `GET /auth/me` to return complete `UserResponse` fields (email, subscription_type)

### Added
- **Test infrastructure** (`tests/`): Complete pytest + pytest-asyncio setup with:
  - `conftest.py`: `async_client` fixture (ASGITransport + mocked DB), `test_db`, `make_token`, `mock_celery_app`, `MockScalarResult` helper
  - `test_api/test_article.py`: 5 tests (list, get, delete CRUD)
  - `test_api/test_auth.py`: 4 tests (valid/invalid/missing token)
  - `test_api/test_collect.py`: 3 tests (success, validation, service call)
  - `test_api/test_publisher.py`: 9 tests (