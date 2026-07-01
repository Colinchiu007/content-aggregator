"""Proxy API 测试 — GET/PUT /api/v1/proxy/config, POST /api/v1/proxy/auto-detect"""

import pytest


class TestProxyConfig:
    """GET /api/v1/proxy/config — 获取代理配置"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_get_proxy_config(self):
        """GET /api/v1/proxy/config 应返回代理配置"""
        resp = await self.client.get("/api/v1/proxy/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "ports" in data
        assert "auto_detect" in data
        assert "detected_proxy" in data
        assert len(data["ports"]) >= 1

    @pytest.mark.asyncio
    async def test_update_proxy_config(self, monkeypatch):
        """PUT /api/v1/proxy/config 应更新代理端口并返回新配置"""
        from app.services.proxy_service import auto_detect_proxy

        async def mock_auto_detect(ports):
            return "socks5://127.0.0.1:9999"

        monkeypatch.setattr(
            "app.api.v1.proxy.auto_detect_proxy",
            mock_auto_detect,
        )

        resp = await self.client.put(
            "/api/v1/proxy/config",
            json={"ports": ["9999", "8888"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "9999" in data["ports"]
        assert "8888" in data["ports"]
        assert data["detected_proxy"] == "socks5://127.0.0.1:9999"

    @pytest.mark.asyncio
    async def test_update_proxy_config_empty_ports(self):
        """空端口列表应返回 422"""
        resp = await self.client.put(
            "/api/v1/proxy/config",
            json={"ports": []},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_update_proxy_config_empty_body(self):
        """空请求体应返回 422"""
        resp = await self.client.put("/api/v1/proxy/config", json={})
        assert resp.status_code == 422


class TestProxyAutoDetect:
    """POST /api/v1/proxy/auto-detect — 代理自动检测"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client, monkeypatch):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

        async def mock_auto_detect(ports=None):
            return "socks5://127.0.0.1:7890"

        monkeypatch.setattr(
            "app.api.v1.proxy.auto_detect_proxy",
            mock_auto_detect,
        )

    @pytest.mark.asyncio
    async def test_auto_detect_success(self):
        """POST /api/v1/proxy/auto-detect 应返回检测结果"""
        resp = await self.client.post("/api/v1/proxy/auto-detect")
        assert resp.status_code == 200
        data = resp.json()
        assert "detected_proxy" in data
        assert "available" in data
        assert "message" in data
        assert data["available"] is True
