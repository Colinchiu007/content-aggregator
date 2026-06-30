# content-aggregator — 开发流程规范

> 内容采集 + AI 改写 + 多平台发布的开发流程与编码约定。AI 工具启动时自动读取。

---

## 核心原则

1. **先文档再代码**：没有 PRD 不动手，没有架构设计不动手
2. **TDD**：测试先于代码，提交前全部测试通过
3. **依赖注入链**：Router → Service → DB，禁止跳过 Service 层直接操作数据库
4. **AI API 隔离**：所有 AI 调用必须通过 `services/rewriter.py`，前端不直接调用
5. **安全第一**：API Key 从环境变量读取，禁止硬编码

## AI 角色分工

| 角色 | 阶段 | 产出物 |
|------|------|--------|
| **PM** | 需求分析 | PRD、用户故事、功能列表 |
| **架构师** | 技术设计 | 模块设计、API 端点、数据流 |
| **后端工程师** | 编码实现 | FastAPI 路由 + Service + 测试 |
| **前端工程师** | 编码实现 | Vue 3 页面 + API 对接 |
| **QA** | 质量验证 | API 测试、前端 E2E |
| **CTO** | 代码评审 | 安全审查、AI API 调用审查 |

## 7 阶段开发流程

### 阶段 1：想法澄清
确认：目标用户、采集来源或改写风格、发布平台、MVP 范围

### 阶段 2：PRD（PM）
产出：PRD，包含 P0/P1/P2 功能列表、API 端点清单、验收标准
**批准后才能进入下一阶段。**

### 阶段 3：技术设计（架构师）
产出：方案对比 + 推荐方案
- 后端：新路由 → Service → DB 设计
- 前端：新页面 → 组件树 → API 对接
**原则：选最简单的方案。**

### 阶段 4：开发计划（PM）
MVP 拆成 ≤4h 的任务，标注依赖关系。

### 阶段 5：编码实现（开发 + TDD）
- 先写测试，再写代码
- API 端点 /health 验证
- 手动验证：核心功能 / 非法输入不崩溃 / 错误提示友好

### 阶段 6：代码评审（CTO）
必检项：
- 🔴 API Key / Token 是否硬编码
- 🔴 AI API 调用是否有 60s 超时
- 🔴 用户输入是否有 Pydantic 验证
- 🟠 异常是否被 catch + logging
- 🟠 Router 是否只做路由，不写逻辑
- 🟢 新增页面是否注册了导航路由

### 阶段 7：发布
- 更新 CHANGELOG.md
- pytest 全部通过
- git 提交并 tag

## 质量门禁

**PRD 阶段**：MVP 范围清晰 / API 端点明确 / 验收标准可验证
**设计阶段**：数据流设计完整 / 简单方案优先
**开发阶段**：测试全通过 / 手动验证核心功能
**Review 阶段**：CRITICAL 问题已修复 / AI API 安全审查通过

## TDD 流程

```
RED   → 在 backend/tests/ 下写失败测试（ASGITransport 模拟请求）
GREEN → 最小实现让测试通过
REFACTOR → 重构，保持测试通过
```

### 测试规范

```python
# backend/tests/test_api/
async def test_collect_url(async_client):
    resp = await async_client.post("/api/v1/collect/url", json={"url": "https://example.com"})
    assert resp.status_code == 200
    assert "title" in resp.json()

async def test_rewrite(async_client):
    resp = await async_client.post("/api/v1/rewrite/", json={
        "content": "原始内容", "style": "轻松易懂"
    })
    assert resp.status_code == 200
```

## 提交规范

```
feat(collector): 添加知乎文章采集
fix(rewriter): 修复 60s 超时不生效
docs: 更新 PRD 改写风格章节
refactor: 统一异常处理
```

## 文档清单

| 文件 | 路径 | 说明 |
|------|------|------|
| AGENTS.md | `./01-docs/AGENTS.md` | 本文件，开发流程规范 |
| CLAUDE.md | `./CLAUDE.md` | 项目上下文和开发命令 |
| .clinerules | `./.clinerules` | 硬约束规则 |
| PRD | `./02-source/PRD/` | 产品需求文档 |
| SPEC.md | `./SPEC.md` | 技术规格说明 |
| API | `./02-source/API/` | API 设计文档 |
| TECH | `./02-source/TECH/` | 技术设计文档 |
| CHANGELOG.md | `./CHANGELOG.md` | 变更日志 |

## 常用命令

```bash
# 后端
cd backend && uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm run dev

# 测试
cd backend && pytest -v

# 数据库迁移
cd backend && alembic upgrade head
```

## 版本

**v2.0** (HotRewrite v2) — Phase 0 骨架搭建完成。
