# Content-Aggregator TDD 开发完成标记

**完成日期**: 2026-06-26
**执行者**: 独立开发 Agent (Cowork subagent)

## 验收清单

- [x] `pytest backend/tests/ -v` — **25 个测试全部通过** (>=15 要求已满足)
- [x] Publisher 不再是 stub — `create_publish_tasks` 现在创建 PublishLog 并派发 Celery 异步任务
- [x] `ca_publish_to_wx` 签名已修复 — 接受 `(article_id, platform)`，与调用方匹配
- [x] 重复模块已清理 — 删除 `collector.py` 和 `rewriter.py`，保留 `collect.py` 和 `rewrite.py`
- [x] pyproject.toml — package source 从 `_archive_v1/src/` 迁移到 `src/`（_archive_v1 已清理）
- [x] CHANGELOG.md 已更新
- [x] PRD 同步 — 因 `02-source/PRD/` 目录不在可访问范围内，CHANGELOG 中记录了所有变更
- [x] 所有更改经过 TDD — 先写测试 → 修复代码 → 全部通过

## 变更文件

### 新增
- `backend/tests/conftest.py` — 测试基础设施
- `backend/tests/test_api/test_article.py` — 5 个测试
- `backend/tests/test_api/test_auth.py` — 4 个测试
- `backend/tests/test_api/test_collect.py` — 3 个测试
- `backend/tests/test_api/test_publisher.py` — 9 个测试
- `backend/tests/test_api/test_rewriter.py` — 4 个测试

### 修改
- `backend/app/services/publisher.py` — 增加 Celery 任务派发逻辑 + `_execute_platform_publish`
- `backend/app/tasks.py` — 修复 `ca_publish_to_wx` 签名，更新 `ca_rewrite_article` 使用 standalone rewrite
- `backend/app/api/v1/collector.py` — 改用 standalone `services/collect.py`
- `backend/app/api/v1/rewriter.py` — 改用 standalone `services/rewrite.py`
- `backend/app/api/v1/auth.py` — 修复 `GET /me` 返回完整 UserResponse
- `backend/app/services/__init__.py` — 更新导出
- `CHANGELOG.md` — 记录所有变更

### 删除
- `backend/app/services/collector.py`
- `backend/app/services/rewriter.py`

## 测试覆盖

| 模块 | 测试数 | 覆盖场景 |
|------|--------|---------|
| articles | 5 | list/get/delete CRUD |
| auth | 4 | token 验证（有效/无效/缺失/格式） |
| collect | 3 | 采集成功、参数验证、服务调用 |
| publisher | 9 | API 调用、Celery 派发、NotFoundError |
| rewriter | 4 | 改写成功、不存在、验证、选项传递 |
| **合计** | **25** | — |
