"""发布 API 测试 — POST /api/v1/publish/ + GET /api/v1/publish/status/{task_id}

同时包含 _execute_platform_publish 的 orchestrator 集成测试。
"""

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


class TestExecutePlatformPublish:
    """_execute_platform_publish — orchestrator API 集成测试"""

    @pytest.mark.asyncio
    async def test_execute_publish_success(self, monkeypatch):
        """调用 orchestrator API 成功时应标记为 success"""
        from app.services.publisher import _execute_platform_publish

        # Mock DB session for publisher module
        mock_log = MagicMock()
        mock_log.status = "pending"
        mock_log.platform = "wechat"

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=mock_log)
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_cm)
        monkeypatch.setattr("app.services.publisher.AsyncSessionLocal", mock_session_factory)

        # Mock httpx.AsyncClient POST
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "task_id": "orch-task-001",
            "status": "pending",
            "platforms": ["wechat_mp"],
        })

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(return_value=mock_response)

        monkeypatch.setattr("httpx.AsyncClient", MagicMock(return_value=mock_client_instance))

        result = await _execute_platform_publish(
            article_id=str(uuid.uuid4()),
            platform="wechat",
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_publish_orchestrator_unreachable(self, monkeypatch):
        """Orchestrator 不可达时应标记为 failed"""
        from app.services.publisher import _execute_platform_publish
        import httpx

        # Mock DB session for publisher module
        mock_log = MagicMock()
        mock_log.status = "pending"
        mock_log.platform = "wechat"

        mock_session = MagicMock()
        mock_session.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=mock_log)
        )
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_cm)
        monkeypatch.setattr("app.services.publisher.AsyncSessionLocal", mock_session_factory)

        # Mock httpx to raise connection error
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(
            side_effect=httpx.RequestError("Connection refused")
        )

        monkeypatch.setattr("httpx.AsyncClient", MagicMock(return_value=mock_client_instance))

        result = await _execute_platform_publish(
            article_id=str(uuid.uuid4()),
            platform="wechat",
        )
        assert result["status"] == "failed"
        assert "error" in result
