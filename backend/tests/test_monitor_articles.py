"""竞品监控文章 API 测试 — MonitorArticle 列表 + 标记已读 + 一键改写 (Phase A: mock DB)"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_list_articles_empty(async_client):
    """获取空文章列表"""
    client, mock_session = async_client
    resp = await client.get("/api/v1/monitor-articles/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_mark_read_not_found(async_client):
    """标记不存在的文章返回 404"""
    client, mock_session = async_client
    from tests.conftest import MockScalarResult

    # Both source query and article query return empty
    mock_session.execute = AsyncMock(
        return_value=MockScalarResult(scalars_list=[])
    )

    resp = await client.post(f"/api/v1/monitor-articles/{uuid.uuid4()}/read")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rewrite_monitor_article(async_client, monkeypatch):
    """一键改写监控文章"""
    client, mock_session = async_client
    from tests.conftest import MockScalarResult

    fake_source_id = uuid.uuid4()
    fake_article_id = uuid.uuid4()

    # Mock: first execute returns source IDs, second returns the article
    call_count = 0

    async def _mock_execute(statement):
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            # Return source IDs
            result = MagicMock()
            result.fetchall = MagicMock(return_value=[(fake_source_id,)])
            return result
        else:
            # Return the article
            fake_article = MagicMock()
            fake_article.id = fake_article_id
            fake_article.source_id = fake_source_id
            fake_article.title = "测试文章标题"
            fake_article.url = "https://example.com/test"
            fake_article.summary = "这是一篇测试文章的摘要内容"
            fake_article.is_read = False
            return MockScalarResult(scalar_one=fake_article)

    mock_session.execute = AsyncMock(side_effect=_mock_execute)
    mock_session.flush = AsyncMock()
    mock_session.add = MagicMock()

    # Mock the Celery app + task (both are imported inside the endpoint)
    mock_task = MagicMock()
    mock_task.delay = MagicMock(return_value=MagicMock(id="mock-task-id"))
    mock_celery = MagicMock()
    monkeypatch.setattr("app.tasks.celery_app", mock_celery)
    monkeypatch.setattr("app.tasks.ca_rewrite_article", mock_task)

    payload = {"style": "轻松易懂"}
    resp = await client.post(
        f"/api/v1/monitor-articles/{fake_article_id}/rewrite",
        json=payload,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["task_id"] == "mock-task-id"
