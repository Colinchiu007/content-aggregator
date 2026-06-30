"""发布 API 测试 — POST /api/v1/publish/ + GET /api/v1/publish/status/{task_id}"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import MockScalarResult


class TestPublishArticle:
    """POST /api/v1/publish/ — 多平台发布文章"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client, monkeypatch):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

        # Mock create_publish_tasks to avoid DB/Celery calls
        async def mock_create_publish_tasks(article_id, user_id, platforms):
            return {
                "task_id": str(article_id),
                "platforms": platforms,
                "task_ids": ["mock-celery-id"],
                "message": f"已为 {len(platforms)} 个平台创建发布任务",
            }

        monkeypatch.setattr(
            "app.api.v1.publisher.create_publish_tasks",
            mock_create_publish_tasks,
        )

    @pytest.mark.asyncio
    async def test_publish_success(self):
        """有效请求应返回 201"""
        article_id = str(uuid.uuid4())
        resp = await self.client.post(
            "/api/v1/publish/",
            json={
                "article_id": article_id,
                "platforms": ["wechat", "zhihu"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "task_id" in data
        assert "platforms" in data
        assert "wechat" in data["platforms"]
        assert "zhihu" in data["platforms"]

    @pytest.mark.asyncio
    async def test_publish_missing_article_id(self):
        """缺少 article_id 应返回 422"""
        resp = await self.client.post(
            "/api/v1/publish/",
            json={"platforms": ["wechat"]},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_publish_empty_platforms(self):
        """空平台列表应返回 422"""
        resp = await self.client.post(
            "/api/v1/publish/",
            json={
                "article_id": str(uuid.uuid4()),
                "platforms": [],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_publish_empty_body(self):
        """空请求体应返回 422"""
        resp = await self.client.post("/api/v1/publish/", json={})
        assert resp.status_code == 422


class TestPublishStatus:
    """GET /api/v1/publish/status/{task_id} — 发布状态查询"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client, monkeypatch):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        async def mock_get_publish_status(article_id):
            return {
                "task_id": str(article_id),
                "logs": [
                    {
                        "id": uuid.uuid4(),
                        "platform": "wechat",
                        "status": "success",
                        "error_message": None,
                        "published_at": now,
                        "created_at": now,
                    },
                    {
                        "id": uuid.uuid4(),
                        "platform": "zhihu",
                        "status": "pending",
                        "error_message": None,
                        "published_at": None,
                        "created_at": now,
                    },
                ],
            }

        monkeypatch.setattr(
            "app.api.v1.publisher.get_publish_status",
            mock_get_publish_status,
        )

    @pytest.mark.asyncio
    async def test_publish_status_success(self):
        """有效的 task_id 应返回发布状态列表"""
        task_id = uuid.uuid4()
        resp = await self.client.get(f"/api/v1/publish/status/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert "logs" in data
        assert len(data["logs"]) == 2

    @pytest.mark.asyncio
    async def test_publish_status_invalid_uuid(self):
        """无效 UUID 应返回 422"""
        resp = await self.client.get("/api/v1/publish/status/not-a-uuid")
        assert resp.status_code == 422
