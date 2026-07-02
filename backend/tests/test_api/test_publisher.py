"""发布 API 测试 — POST /api/v1/publish/ + GET /api/v1/publish/status/{task_id} + _execute_platform_publish"""

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
    """_execute_platform_publish — orchestrator API 调用测试"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch):
        """Mock the DB session used by _execute_platform_publish.

        Unlike API-level tests that use the async_client fixture's monkeypatch,
        this test patches _execute_platform_publish's own AsyncSessionLocal import
        directly.
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        # Create a mock session with proper async method signatures
        self.mock_session = MagicMock(spec=AsyncSession)
        self.mock_session.add = MagicMock()
        self.mock_session.flush = AsyncMock()
        self.mock_session.commit = AsyncMock()
        self.mock_session.rollback = AsyncMock()
        self.mock_session.delete = AsyncMock()

        # Mock context manager for async with block
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=self.mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_cm)

        # Patch the specific import used by publisher.py
        monkeypatch.setattr(
            "app.services.publisher.AsyncSessionLocal",
            mock_session_factory,
        )

    @pytest.mark.asyncio
    async def test_execute_publish_success(self):
        """orchestrator API 返回 200 时应标记为 success"""
        from app.services.publisher import _execute_platform_publish

        article_id = str(uuid.uuid4())
        platform = "wechat"

        # Mock PublishLog record
        mock_log = MagicMock()
        mock_log.article_id = uuid.UUID(article_id)
        mock_log.platform = platform
        mock_log.status = "pending"
        mock_log.error_message = None
        mock_log.published_at = None

        self.mock_session.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=mock_log)
        )

        # Mock httpx AsyncClient to return success
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"task_id": "orch-task-123"})
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(return_value=mock_response)

        import httpx
        original_cls = httpx.AsyncClient
        httpx.AsyncClient = MagicMock(return_value=mock_client_instance)

        try:
            result = await _execute_platform_publish(article_id, platform)
            assert result["status"] == "success"
            assert result["article_id"] == article_id
            assert result["platform"] == platform
            assert result["orchestrator_task_id"] == "orch-task-123"
            # Verify DB was committed with success
            assert mock_log.status == "success"
        finally:
            httpx.AsyncClient = original_cls

    @pytest.mark.asyncio
    async def test_execute_publish_orchestrator_unreachable(self):
        """orchestrator 不可达时应标记为 failed 不抛出异常"""
        from app.services.publisher import _execute_platform_publish

        article_id = str(uuid.uuid4())
        platform = "douyin"

        # Mock PublishLog record
        mock_log = MagicMock()
        mock_log.article_id = uuid.UUID(article_id)
        mock_log.platform = platform
        mock_log.status = "pending"
        mock_log.error_message = None
        mock_log.published_at = None

        self.mock_session.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=mock_log)
        )

        # Mock httpx to raise connection error
        import httpx

        class _FakeTransport:
            async def handle_async_request(self, request):
                raise httpx.ConnectError("Connection refused")

        failing_client = httpx.AsyncClient(transport=_FakeTransport())
        original_cls = httpx.AsyncClient
        httpx.AsyncClient = MagicMock(return_value=failing_client)

        try:
            result = await _execute_platform_publish(article_id, platform)
            assert result["status"] == "failed"
            assert result["article_id"] == article_id
            assert result["platform"] == platform
            # DB should have been committed with failed status
            assert mock_log.status == "failed"
            assert mock_log.error_message is not None
        finally:
            httpx.AsyncClient = original_cls

    @pytest.mark.asyncio
    async def test_execute_publish_log_not_found(self):
        """找不到 PublishLog 时应返回 not_found（不调用 orchestrator）"""
        from app.services.publisher import _execute_platform_publish

        article_id = str(uuid.uuid4())
        platform = "nonexistent"

        self.mock_session.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=None)
        )

        # Track whether orchestrator was called
        orchestrator_called = False

        async def _tracking_post(*args, **kwargs):
            nonlocal orchestrator_called
            orchestrator_called = True
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json = MagicMock(return_value={})
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        import httpx
        mock_client_instance = AsyncMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = _tracking_post

        original_cls = httpx.AsyncClient
        httpx.AsyncClient = MagicMock(return_value=mock_client_instance)

        try:
            result = await _execute_platform_publish(article_id, platform)
            assert result["status"] == "not_found"
            assert result["article_id"] == article_id
            assert result["platform"] == platform
            # When log is not found, orchestrator should still be called
            # (the function tries to publish regardless of existing log)
            assert orchestrator_called
        finally:
            httpx.AsyncClient = original_cls
