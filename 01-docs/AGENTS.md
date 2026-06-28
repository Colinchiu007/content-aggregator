# content-aggregator (HotRewrite v2) — 开发规范

> 内容采集 + AI 改写 + 多平台发布平台

## 项目定位

HotRewrite v2 是一站式内容改写与发布平台，属于一站式视频生成平台的内容生产环节。用户通过 URL 或手动输入内容，经 AI 改写后发布到多平台。

数据流: **URL 采集 → AI 改写 → 多平台发布**

## 技术栈

| 层 | 技术 |
|----|------|
| **后端** | Python 3.12+ / FastAPI / SQLAlchemy 2.0 (async) |
| **前端** | Vue 3 + TypeScript + Element Plus + Pinia + Vue Router |
| **数据库** | PostgreSQL 15 (asyncpg) |
| **缓存** | Redis 7 |
| **AI** | OpenAI 兼容 API (gpt-4o-mini 等) |
| **迁移** | Alembic |

## 目录结构

```
content-aggregator/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory (create_app)
│   │   ├── config.py            # pydantic-settings 配置
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── api/
│   │   │   ├── deps.py          # get_db, get_current_user DI
│   │   │   └── v1/
│   │   │       ├── router.py    # 路由聚合 + /health
│   │   │       ├── auth.py      # 注册/登录/用户信息
│   │   │       ├── articles.py  # 文章 CRUD
│   │   │       ├── collector.py # URL 采集
│   │   │       ├── rewriter.py  # AI 改写
│   │   │       └── publisher.py # 发布
│   │   ├── core/
│   │   │   ├── security.py      # JWT (HS256) + bcrypt
│   │   │   └── exceptions.py    # 异常层次
│   │   ├── models/              # ORM: User, Article, PublishLog
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   └── services/
│   │       ├── collector.py     # httpx + trafilatura 网页抓取
│   │       ├── rewriter.py      # LLM API 调用 (60s 超时)
│   │       └── publisher.py     # 发布任务管理
│   ├── tests/
│   │   ├── conftest.py          # async_client (ASGITransport)
│   │   └── test_api/            # 测试用例（待补充）
│   └── alembic/                 # 数据库迁移
├── frontend/
│   ├── src/
│   │   ├── router/index.ts      # 7 条路由，含 auth guard
│   │   ├── views/               # 7 个页面
│   │   ├── components/          # UI 组件
│   │   ├── api/                 # Axios + 拦截器
│   │   ├── stores/              # Pinia 状态管理
│   │   └── types/               # TypeScript 类型定义
│   └── tests/
├── 02-source/                   # PRD、架构设计、商业分析文档
└── src/                         # v1 content_aggregator 包源码
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 登录（返回 JWT） |
| GET | `/api/v1/auth/me` | 当前用户信息 |
| POST | `/api/v1/collect/url` | URL 内容采集 |
| POST | `/api/v1/rewrite/` | AI 改写 |
| POST | `/api/v1/publish/` | 创建发布任务 |
| GET | `/api/v1/publish/status/{id}` | 发布状态查询 |
| GET | `/api/v1/articles/` | 文章列表（分页） |
| GET | `/api/v1/articles/{id}` | 文章详情 |
| DELETE | `/api/v1/articles/{id}` | 删除文章 |
| GET | `/api/v1/health` | 健康检查 |

## 核心流程

### 采集 (Collector)

- `collect_from_url()` — httpx GET + trafilatura extract
- 15s 超时，Chrome UA，支持重定向
- 返回结构化内容: title, content (Markdown), word_count

### 改写 (Rewriter)

- 4 种风格: 轻松易懂、正式严谨、吸引眼球、深度分析
- 3 种长度策略: keep (±10%)、compress (-30%)、expand (+30%)
- OpenAI 兼容 API，60s 超时，temperature 0.7，max 4096 tokens
- 支持 SEO 优化标志

### 发布 (Publisher)

- MVP 阶段仅创建 PublishLog 记录（status=pending）
- 实际平台发布延后到 Phase 2

## 关键约定

### 依赖注入链

Router → Depends(get_db) + Depends(get_current_user) → Service
不要在 Router 或 Service 中直接访问数据库，通过 `deps.py` 注入。

### 异常层次

```
HotRewriteException (基类)
├── NotFoundError (404)
├── UnauthorizedError (401)
├── ForbiddenError (403)
├── ConflictError (409)
├── ValidationError (422)
├── ServiceError (502)
└── CollectError (502)
```

### JWT 认证

- 算法: HS256，密钥来自 `SECRET_KEY` 环境变量
- Token 结构: `{sub: user_uuid, username, exp}`
- 有效期: 默认 60 分钟
- 通过 `Depends(get_current_user)` 保护端点

### 数据库

- 异步 SQLAlchemy 2.0 (`AsyncSessionLocal`)
- 连接池: 20 + 10 overflow
- 自动 commit/rollback（`get_db` async generator）

## 环境变量

见 `backend/app/config.py`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | postgresql+asyncpg://... | PostgreSQL 连接 |
| `REDIS_URL` | redis://localhost:6379/0 | Redis 连接 |
| `SECRET_KEY` | change-me-... | JWT 签名密钥 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | JWT 有效期 |
| `OPENAI_API_KEY` | "" | LLM API 密钥 |
| `OPENAI_BASE_URL` | https://api.openai.com/v1 | LLM 端点 |
| `OPENAI_MODEL` | gpt-4o-mini | LLM 模型 |
| `PORT` | 8000 | 服务端口 |
| `CORS_ORIGINS` | localhost:5173,3000 | 允许的跨域来源 |

## 常用命令

```bash
# 安装后端
cd backend && pip install -e .

# 启动
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev

# 测试
cd backend && pytest -v

# 数据库迁移
cd backend && alembic upgrade head

# Docker (PostgreSQL + Redis + 后端)
docker-compose up -d
```

## 开发状态

- **Phase 0**: 项目骨架搭建完成（2026-06-15）
- **MVP**: API 功能可用，测试框架已搭建但测试用例待补充
- **待办**: 补充测试、实际发布平台对接（Phase 2）
- **测试**: 测试框架（pytest + pytest-asyncio + ASGITransport）就绪
