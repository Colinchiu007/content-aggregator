# 热文改写一站式平台 (HotRewrite)

> **内容采集 → AI 改写 → 多平台发布，一站式完成**
>
> 帮助内容创作者快速将优质文章进行AI改写，并一键发布到多个平台的内容生产力工具。

---

## 🎯 项目方向 (v2)

本项目当前处于 **v2 设计阶段**。v1 "Content Aggregator"（Python + Jinja2 + SQLite）代码已清理，参见 Git 历史。

v2 目标：**热文改写一站式平台**，技术栈迁移至 **Vue 3 + PostgreSQL**。

### 当前设计文档

| 文档 | 路径 |
|------|------|
| **PRD (产品需求文档)** | [`02-source/PRD/PROJECT-001-PRD-2026-06-15.md`](02-source/PRD/PROJECT-001-PRD-2026-06-15.md) |
| 竞品分析 | [`02-source/competitor-analysis/`](02-source/competitor-analysis/) |
| 产品设计思路 | [`02-source/PROJECT-001-产品设计思路-2026-06-15.md`](02-source/PROJECT-001-产品设计思路-2026-06-15.md) |
| 架构设计 | [`02-source/TECH/`](02-source/TECH/) |
| 业务需求 | [`02-source/BUSINESS/`](02-source/BUSINESS/) |

---

## 🧭 v2 核心功能规划

### 内容输入
- URL 采集（公众号、知乎、掘金、头条等）
- 粘贴文本 / 文件上传
- 热榜发现（Phase 2）

### AI 改写
- 多风格选择（公众号/知乎/小红书/短视频文案等）
- 长度控制 + 高级选项（SEO 优化）
- 改写预览 + 手动编辑

### 多平台发布
- 平台账号绑定
- 一键发布 / 定时发布
- 发布日志与状态跟踪

### 内容管理
- 素材库（Phase 2）
- 改写历史
- 竞品监控（Phase 2）

---

## 🏗️ 技术栈 (v2)

| 模块 | 技术 | 说明 |
|------|------|------|
| **前端** | Vue 3 + TypeScript + Element Plus + Vite | SPA，Composition API + `<script setup>` |
| **后端** | FastAPI (Python 3.12+) + SQLAlchemy 2.0 (async) | 异步 API 服务 |
| **数据库** | PostgreSQL 15 | 关系型数据存储 |
| **缓存** | Redis 7 | 会话/热点数据缓存 |
| **认证** | JWT (python-jose + passlib/bcrypt) | 用户登录鉴权 |
| **采集** | httpx + trafilatura | 异步 HTTP + HTML 正文提取 |
| **AI** | OpenAI-compatible API (通义千问/DeepSeek) | 多风格改写 |
| **部署** | Docker Compose + Nginx | 一键部署 |

---

## 📁 仓库结构

```
Project001-HotRewrite/
├── README.md              ← 你在这里
├── docker-compose.yml     # PostgreSQL 15 + Redis 7
├── backend/               # FastAPI 后端 (v2)
│   ├── app/
│   │   ├── main.py        # FastAPI app factory
│   │   ├── config.py      # pydantic-settings 配置
│   │   ├── database.py    # 异步 SQLAlchemy 引擎
│   │   ├── models/        # ORM 模型 (User, Article, PublishLog)
│   │   ├── schemas/       # Pydantic 请求/响应模型
│   │   ├── api/v1/        # API 路由 (auth, articles, collector, rewriter, publisher)
│   │   ├── services/      # 业务逻辑层 (collector, rewriter, publisher)
│   │   └── core/          # JWT 安全 + 异常处理
│   ├── alembic/           # 数据库迁移
│   ├── tests/             # pytest 测试
│   ├── pyproject.toml     # Python 依赖
│   └── Dockerfile
├── frontend/              # Vue 3 前端 (v2)
│   ├── src/
│   │   ├── views/         # 7 个页面 (Home, Login, Rewrite, History, Publish, Settings, Register)
│   │   ├── components/    # UI 组件 (UrlInput, StyleSelector, RewriteResult, PublishPanel...)
│   │   ├── api/           # Axios API 客户端 (auth, articles, collector, rewriter, publisher)
│   │   ├── stores/        # Pinia 状态管理 (user, article)
│   │   ├── router/        # Vue Router (7 路由 + 鉴权守卫)
│   │   ├── types/         # TypeScript 接口定义
│   │   └── utils/         # 工具函数
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── 01-docs/               # Agent 开发规范、迁移文档
├── 02-source/             # v2 设计资产（PRD、架构、竞品分析）
│   ├── PRD/               # 产品需求文档
│   ├── TECH/              # 技术架构
│   ├── BUSINESS/          # 业务需求
│   ├── competitor-analysis/  # 竞品分析
│   └── UI/                # 界面设计
├── 03-memory/             # 会话记忆导出
└── CHANGELOG.md           # 变更记录
```

---

## 🚀 快速开始

### 环境要求
- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Docker Compose（推荐）
```bash
# 启动 PostgreSQL + Redis
docker compose up -d

# 后端
cd backend
cp .env.example .env      # 填写 OPENAI_API_KEY 等
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev               # → http://localhost:3000
```

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 登录获取 JWT |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| POST | `/api/v1/collect/url` | URL 采集 |
| POST | `/api/v1/rewrite/` | AI 改写 |
| POST | `/api/v1/publish/` | 多平台发布 |
| GET | `/api/v1/articles/` | 文章列表 |
| GET | `/api/v1/health` | 健康检查 |

---

## 🚀 路线图

| 阶段 | 时间 | 核心功能 |
|------|------|---------|
| **MVP** | 第 1-3 周 | URL 采集 + AI 改写 + 发布 |
| **内测** | 第 4 周 | 邀请 10 用户测试 |
| **公测** | 第 5-8 周 | 开放注册 |
| **Phase 2** | 第 9-12 周 | 热榜 + 素材库 + 竞品监控 |
| **Phase 3** | 第 13-18 周 | 团队协作 + 商业化 |

---

