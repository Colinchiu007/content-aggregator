# 项目: content-aggregator
# 目标: 修复 PRD 差距 — 测试覆盖 / package.json / publisher 空桩 / v1 采集器集成 / Alembic migration
# 创建: 2026-06-30

## 任务依赖 DAG

```
T1 (package.json) ──→ T8 (前端构建验证)
                        │
T2 (test_auth, test_auth_password) ──→ T6 (全量回归)
T3 (test_article, test_collect)     ──→ T6
T4 (test_rewriter, test_publisher)  ──→ T6
T5 (test_proxy, test_task_cancel)   ──→ T6
                        │
T6 (全量回归验证: pytest backend/tests/ -v) ──→ T9 (PRD/CHANGELOG 同步)
                        │
T7 (publisher 空桩修复 ──对接 orchestrator API) ──→ T6 重跑
                        │
T10 (v1 legacy 采集器接入) ──→ T11 (Alembic 初始迁移)
                        │
T11 (Alembic 初始迁移) ──→ T6 重跑
```

T2-T5 可并行执行（无互相依赖），T6 等待 T2-T5 全部完成。
T7 依赖 T6（确保现有测试不破坏），T10/T11 可在 T7 后独立处理。
T8 在 T1 后即可直接验证。
T9 所有任务完成后执行。

## 任务清单

| # | 任务 | 依赖 | 风险 | PRD | 测试 | 模式 | 验证标准 | 状态 |
|---|------|------|------|-----|------|------|---------|------|
| 1 | P0: 恢复 frontend/package.json | - | low | no | no | auto | vue-ts 构建 `cd frontend && npm install && npm run build` 成功 | pending |
| 2 | P0: 恢复 test_auth.py + test_auth_password.py | - | low | no | yes | tdd | `pytest backend/tests/test_api/test_auth.py -v` ALL GREEN | pending |
| 3 | P0: 恢复 test_article.py + test_collect.py | - | low | no | yes | tdd | `pytest backend/tests/test_api/test_article.py backend/tests/test_api/test_collect.py -v` ALL GREEN | pending |
| 4 | P0: 恢复 test_rewriter.py + test_publisher.py | - | low | no | yes | tdd | `pytest backend/tests/test_api/test_rewriter.py backend/tests/test_api/test_publisher.py -v` ALL GREEN | pending |
| 5 | P0: 恢复 test_proxy.py + test_task_cancel.py | - | low | no | yes | tdd | `pytest backend/tests/test_api/test_proxy.py backend/tests/test_api/test_task_cancel.py -v` ALL GREEN | pending |
| 6 | P0: 全量回归验证 | 2,3,4,5 | low | no | yes | tdd | `cd backend && pytest tests/ -v --tb=short` ALL GREEN (≥30 tests) | pending |
| 7 | P1: 修复 publisher 空桩 → 对接 orchestrator API | 6 | med | yes | yes | tdd | `_execute_platform_publish` 调用 orchestrator publish API，测试覆盖 mock 场景 | pending |
| 8 | P0: 验证 frontend 构建 | 1 | low | no | no | auto | `cd frontend && npm install && npm run build` 成功 | pending |
| 9 | PRD/CHANGELOG 同步（全任务） | 6,7,8,10,11 | low | yes | no | self-check | PRD 差距标记已修复，CHANGELOG 条目完整 | pending |
| 10 | P2: 接入 v1 legacy 采集器（14 平台 → v2 bridge） | 6 | med | yes | yes | tdd | 新 bridge 模块导入 v1 全部 collectors，`src/` 依赖可导入，测试覆盖 5+ 平台 | pending |
| 11 | P2: 创建初始 Alembic migration + fix 现有 migration 依赖 | 6 | med | yes | no | tdd | `alembic history` 显示完整链，`alembic upgrade head` 成功（自动空转验证） | pending |

## 说明

- FUSE 约束：所有写操作必须通过 Python heredoc 写入，然后 `python3 -c "import ast; ast.parse(open('file').read())"` 验证。见 `.plan/knowledge/project-rules.md`
- FUSE git 约束：git 写操作在 /tmp 克隆中进行。`git clone D:\Data\projects\content-aggregator /tmp/ca-fix`，改完后 `git push` 回到主仓库。
- 测试风格参照 `backend/tests/test_monitors.py`：使用 `async_client` fixture，mock DB session，Class 组织，`@pytest.mark.asyncio`
- 目标：全量测试 ≥30 用例，ALL GREEN
- v1 采集器在 `src/content_aggregator/sources/collectors/`（14 个平台），通过 bridge 模块导入到 v2 的 `app/services/collect.py` 管道中
- 现有 Alembic migration `001_create_monitor_tables` 依赖 `2f5952d46af4` 但不存 — 需创建初始 migration 作为父级并修正 down_revision
