"""文章 API 测试 — GET/DELETE /api/v1/articles"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import MockScalarResult


class TestListArticles:
    """GET /api/v1/articles/ — 获取文章列表"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_list_articles_success(self):
        """GET /api/v1/articles/ 应返回分页文章列表"""
        resp = await self.client.get("/api/v1/articles/")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.asyncio
    async def test_list_articles_with_pagination(self):
        """分页参数应生效"""
        resp = await self.client.get("/api/v1/articles/?page=2&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_articles_unauthorized(self):
        """无 token 应返回 401"""
        old = self.client.headers.pop("Authorization")
        resp = await self.client.get("/api/v1/articles/")
        assert resp.status_code == 401
        self.client.headers["Authorization"] = old


class TestGetArticle:
    """GET /api/v1/articles/{article_id} — 获取文章详情"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db
        import uuid as _uuid
        from datetime import datetime, timezone
        self.fake_article_id = _uuid.uuid4()
        self.fake_article = MagicMock()
        self.fake_article.id = self.fake_article_id
        self.fake_article.user_id = _uuid.uuid4()
        self.fake_article.source_type = "url"
        self.fake_article.source_content = "Test content"
        self.fake_article.source_url = "https://example.com"
        self.fake_article.rewrite_style = None
        self.fake_article.rewrite_length = None
        self.fake_article.result_content = None
        self.fake_article.word_count_original = 100
        self.fake_article.word_count_result = None
        self.fake_article.created_at = datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_get_article_found(self):
        """存在的文章应返回 200"""
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=self.fake_article)
        )
        resp = await self.client.get(f"/api/v1/articles/{self.fake_article_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    @pytest.mark.asyncio
    async def test_get_article_not_found(self):
        """不存在的文章应返回 404"""
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=None)
        )
        resp = await self.client.get(f"/api/v1/articles/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_article_invalid_uuid(self):
        """无效 UUID 应返回 422"""
        resp = await self.client.get("/api/v1/articles/not-a-uuid")
        assert resp.status_code == 422


class TestDeleteArticle:
    """DELETE /api/v1/articles/{article_id} — 删除文章"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_delete_article_not_found(self):
        """不存在的文章应返回 404"""
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=None)
        )
        resp = await self.client.delete(f"/api/v1/articles/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_article_invalid_uuid(self):
        """无效 UUID 应返回 422"""
        resp = await self.client.delete("/api/v1/articles/not-a-uuid")
        assert resp.status_code == 422
