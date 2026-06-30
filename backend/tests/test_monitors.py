"""MonitorSource CRUD API 测试 (Phase A: mock DB)"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMonitorSourceAPI:
    """MonitorSource CRUD API 测试"""

    MONITOR_SOURCE_PAYLOAD = {
        "name": "科技竞品A",
        "source_type": "wechat",
        "identifier": "keji_jingpin_a",
    }

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        """Setup mocks for each test"""
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db
        return client

    # ── CREATE ──

    @pytest.mark.asyncio
    async def test_create_monitor_source(self, make_token, sample_user_id):
        """POST /api/v1/monitors/ 应创建监控源并返回 201"""
        from app.models.monitor_source import MonitorSource
        import uuid as _uuid

        source_id = _uuid.uuid4()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        # Mock flush + refresh to set id and timestamps
        async def _refresh_side_effect(obj):
            obj.id = source_id
            obj.created_at = now
            obj.updated_at = now

        self.mock_db.flush = AsyncMock()
        self.mock_db.refresh = AsyncMock(side_effect=_refresh_side_effect)

        resp = await self.client.post(
            "/api/v1/monitors/",
            json=self.MONITOR_SOURCE_PAYLOAD,
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "科技竞品A"
        assert data["source_type"] == "wechat"
        assert data["identifier"] == "keji_jingpin_a"
        assert data["id"] == str(source_id)

    # ── LIST ──

    @pytest.mark.asyncio
    async def test_list_monitor_sources(self):
        """GET /api/v1/monitors/ 应返回监控源列表"""
        resp = await self.client.get("/api/v1/monitors/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    # ── GET ──

    @pytest.mark.asyncio
    async def test_get_monitor_source_not_found(self):
        """GET /api/v1/monitors/{id} 不存在应返回 404"""
        fake_id = str(uuid.uuid4())
        resp = await self.client.get(f"/api/v1/monitors/{fake_id}")
        assert resp.status_code == 404

    # ── UPDATE ──

    @pytest.mark.asyncio
    async def test_update_monitor_source_not_found(self):
        """PUT /api/v1/monitors/{id} 不存在应返回 404"""
        fake_id = str(uuid.uuid4())
        resp = await self.client.put(
            f"/api/v1/monitors/{fake_id}",
            json={"name": "新名字"},
        )
        assert resp.status_code == 404

    # ── DELETE ──

    @pytest.mark.asyncio
    async def test_delete_monitor_source_not_found(self):
        """DELETE /api/v1/monitors/{id} 不存在应返回 404"""
        fake_id = str(uuid.uuid4())
        resp = await self.client.delete(f"/api/v1/monitors/{fake_id}")
        assert resp.status_code == 404

    # ── SEARCH ──

    @pytest.mark.asyncio
    async def test_list_monitors_with_search(self):
        """GET /api/v1/monitors/?search=xxx 应正常响应"""
        resp = await self.client.get("/api/v1/monitors/?search=科技")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    # ── VALIDATION ──

    @pytest.mark.asyncio
    async def test_create_monitor_missing_identifier(self):
        """缺少 identifier 应返回 422"""
        resp = await self.client.post(
            "/api/v1/monitors/",
            json={"name": "测试", "source_type": "wechat"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_monitor_empty_body(self):
        """空请求体应返回 422"""
        resp = await self.client.post("/api/v1/monitors/", json={})
        assert resp.status_code == 422
