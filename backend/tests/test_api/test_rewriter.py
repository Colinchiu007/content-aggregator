"""改写 API 测试 — POST /api/v1/rewrite/"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import MockScalarResult


class TestRewriteArticle:
    """POST /api/v1/rewrite/ — AI 文章改写"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client, monkeypatch):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

        # Mock rewrite_content to avoid real LLM calls
        from app.services.rewrite import RewriteResult

        async def mock_rewrite(content="", style="轻松易懂", length="keep", seo_optimize=False, **kwargs):
            return RewriteResult(
                result_content="这是改写后的内容。包含了更清晰的语言和更好的结构。",
                word_count=25,
                style=style,
                length=length,
            )

        monkeypatch.setattr("app.api.v1.rewriter.rewrite_content", mock_rewrite)

    @pytest.mark.asyncio
    async def test_rewrite_success(self):
        """有效请求应返回 200 和改写结果"""
        article_id = uuid.uuid4()

        # Mock article existence check
        fake_article = MagicMock()
        fake_article.id = article_id
        fake_article.source_content = "Original article content for rewriting."
        fake_article.rewrite_style = None
        fake_article.rewrite_length = None
        fake_article.result_content = None
        fake_article.word_count_result = None
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=fake_article)
        )

        resp = await self.client.post(
            "/api/v1/rewrite/",
            json={
                "article_id": str(article_id),
                "style": "轻松易懂",
                "length": "keep",
                "seo_optimize": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "result_content" in data
        assert "word_count" in data
        assert data["style"] == "轻松易懂"

    @pytest.mark.asyncio
    async def test_rewrite_article_not_found(self):
        """不存在的文章应返回 404"""
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=None)
        )

        resp = await self.client.post(
            "/api/v1/rewrite/",
            json={
                "article_id": str(uuid.uuid4()),
                "style": "轻松易懂",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_rewrite_missing_article_id(self):
        """缺少 article_id 应返回 422"""
        resp = await self.client.post(
            "/api/v1/rewrite/",
            json={"style": "轻松易懂"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rewrite_empty_body(self):
        """空请求体应返回 422"""
        resp = await self.client.post("/api/v1/rewrite/", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rewrite_invalid_style(self):
        """无效改写风格也接受（由 LLM 侧处理）"""
        article_id = uuid.uuid4()
        fake_article = MagicMock()
        fake_article.id = article_id
        fake_article.source_content = "Some content"
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalar_one=fake_article)
        )

        resp = await self.client.post(
            "/api/v1/rewrite/",
            json={
                "article_id": str(article_id),
                "style": "unknown_style_xxx",
            },
        )
        # The mock returns success since we mock rewrite_content
        assert resp.status_code == 200
