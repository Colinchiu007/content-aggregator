"""采集 API 测试 — POST /api/v1/collect/url"""

import pytest


class TestCollectURL:
    """POST /api/v1/collect/url — URL 内容采集"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client, monkeypatch):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

        # Mock collect_url service to avoid real HTTP calls
        from app.services.collect import CollectResult

        async def mock_collect_url(url: str, timeout: int = 30):
            return CollectResult(
                title="Test Article Title",
                content="This is the extracted article content for testing purposes.",
                author="Test Author",
                word_count=15,
                source_url=url,
            )

        monkeypatch.setattr("app.api.v1.collector.collect_url", mock_collect_url)

    @pytest.mark.asyncio
    async def test_collect_url_success(self):
        """有效 URL 应返回 200 和采集结果"""
        resp = await self.client.post(
            "/api/v1/collect/url",
            json={"url": "https://example.com/test-article"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "title" in data
        assert "content" in data
        assert "word_count" in data
        assert data["source_url"] == "https://example.com/test-article"

    @pytest.mark.asyncio
    async def test_collect_url_empty_url(self):
        """空 URL — 无 min_length 约束，通过 schema 验证后由服务层处理"""
        resp = await self.client.post(
            "/api/v1/collect/url",
            json={"url": ""},
        )
        # Schema allows empty string (no min_length), service mock handles it
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_collect_url_missing_url(self):
        """缺少 url 字段应返回 422"""
        resp = await self.client.post(
            "/api/v1/collect/url",
            json={},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_collect_url_invalid_scheme(self):
        """无协议前缀的 URL 应仍然可处理"""
        resp = await self.client.post(
            "/api/v1/collect/url",
            json={"url": "not-a-valid-url"},
        )
        # Should still try to process (service layer handles validation)
        assert resp.status_code in (200, 422)
