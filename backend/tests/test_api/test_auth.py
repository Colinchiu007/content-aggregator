"""认证 API 测试 — GET /api/v1/auth/me"""

import pytest


class TestAuthMe:
    """GET /api/v1/auth/me — 获取当前用户信息"""

    MONITOR_SOURCE_PAYLOAD = {
        "name": "科技竞品A",
        "source_type": "wechat",
        "identifier": "keji_jingpin_a",
    }

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_get_me_success(self):
        """GET /api/v1/auth/me 应返回当前用户信息"""
        resp = await self.client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "username" in data

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self):
        """GET /api/v1/auth/me 无 token 应返回 401"""
        client = self.client
        client.headers.pop("Authorization")
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        # Restore header for subsequent tests
        from tests.conftest import create_access_token
        client.headers["Authorization"] = f"Bearer {create_access_token('test-user')}"

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self):
        """GET /api/v1/auth/me 无效 token 应返回 401"""
        client = self.client
        old = client.headers.get("Authorization")
        client.headers["Authorization"] = "Bearer invalid-token-here"
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
        # Restore
        client.headers["Authorization"] = old
