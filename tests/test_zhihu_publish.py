"""
Tests for Zhihu publisher.

Following TDD workflow:
1. Write tests first (this file)
2. Run tests (they should fail)
3. Write code to make tests pass
4. Run tests (they should pass)
5. Refactor (optional)
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the publisher class
from content_aggregator.publishers.zhihu import ZhihuPublisher, ZhihuAPIError
from content_aggregator.models.publish import PublishResult


class TestZhihuPublisher:
    """Test cases for ZhihuPublisher."""

    @pytest.fixture
    def publisher(self):
        """Create ZhihuPublisher instance with mock credentials."""
        return ZhihuPublisher(
            client_id="zhihu_client_12345",
            client_secret="zhihu_secret_67890",
            username="test_user",
            password="test_pass"
        )

    @pytest.fixture
    def sample_article(self):
        """Sample article for testing."""
        return {
            "id": 123,
            "title": "Test Article Title",
            "content": "<p>This is test content for Zhihu.</p>",
            "summary": "Test summary",
            "tags": ["AI", "Technology"],
            "cover_image": "/path/to/cover.jpg"
        }

    @pytest.fixture
    def mock_access_token(self):
        """Mock access token response."""
        return {
            "access_token": "zhihu_mock_token_12345",
            "token_type": "bearer",
            "expires_in": 86400,
            "refresh_token": "zhihu_mock_refresh_token"
        }

    # ===== Test Cases for __init__ =====

    def test_init_success(self, publisher):
        """Given valid credentials, when init, then set all fields."""
        assert publisher.client_id == "zhihu_client_12345"
        assert publisher.client_secret == "zhihu_secret_67890"
        assert publisher.username == "test_user"
        assert publisher.password == "test_pass"
        assert publisher.access_token is None
        assert publisher.token_expires_at == 0

    def test_init_empty_client_id(self):
        """Given empty client_id, when init, then raise ValueError."""
        with pytest.raises(ValueError, match="client_id cannot be empty"):
            ZhihuPublisher(client_id="", client_secret="test_secret", username="user", password="pass")

    def test_init_empty_client_secret(self):
        """Given empty client_secret, when init, then raise ValueError."""
        with pytest.raises(ValueError, match="client_secret cannot be empty"):
            ZhihuPublisher(client_id="test_id", client_secret="", username="user", password="pass")

    # ===== Test Cases for get_access_token() ======

    @pytest.mark.asyncio
    async def test_get_access_token_success(self, publisher, mock_access_token):
        """Given valid credentials, when get_access_token, then return token."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = mock_access_token
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            token = await publisher.get_access_token()

            assert token == "zhihu_mock_token_12345"
            assert publisher.access_token == "zhihu_mock_token_12345"
            assert publisher.token_expires_at > 0

    @pytest.mark.asyncio
    async def test_get_access_token_api_error(self, publisher):
        """Given API returns error, when get_access_token, then raise ZhihuAPIError."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {
                "error": "invalid_client",
                "error_description": "Client authentication failed"
            }
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response

            with pytest.raises(ZhihuAPIError, match="Client authentication failed"):
                await publisher.get_access_token()

    @pytest.mark.asyncio
    async def test_get_access_token_network_error(self, publisher):
        """Given network error, when get_access_token, then raise ZhihuAPIError."""
        with patch("httpx.AsyncClient.post") as mock_post:
            import httpx
            mock_post.side_effect = httpx.ConnectError("Network error")

            with pytest.raises(ZhihuAPIError, match="Failed to get access token"):
                await publisher.get_access_token()

    @pytest.mark.asyncio
    async def test_get_access_token_cached(self, publisher, mock_access_token):
        """Given token already cached and not expired, when get_access_token, then return cached token."""
        # Set cached token
        publisher.access_token = "cached_token"
        publisher.token_expires_at = datetime.now().timestamp() + 3600

        with patch("httpx.AsyncClient.post") as mock_post:
            token = await publisher.get_access_token()

            assert token == "cached_token"
            mock_post.assert_not_called()  # Should not call API

    # ===== Test Cases for publish() ======

    @pytest.mark.asyncio
    async def test_publish_success(self, publisher, sample_article, mock_access_token):
        """Given valid article, when publish, then return PublishResult with success."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch("httpx.AsyncClient.post") as mock_post:
                # Mock create article response
                mock_response = Mock()
                mock_response.json.return_value = {
                    "article_id": "1234567890123456789",
                    "url": "https://zhuanlan.zhihu.com/p/1234567890123456789"
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                result = await publisher.publish(sample_article)

                assert isinstance(result, PublishResult)
                assert result.status == "success"
                assert result.url == "https://zhuanlan.zhihu.com/p/1234567890123456789"
                assert result.platform == "zhihu"

    @pytest.mark.asyncio
    async def test_publish_api_error(self, publisher, sample_article, mock_access_token):
        """Given API returns error, when publish, then return PublishResult with failed."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "error": "article_too_short",
                    "error_description": "Article content is too short"
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                result = await publisher.publish(sample_article)

                assert isinstance(result, PublishResult)
                assert result.status == "failed"
                assert "Article content is too short" in result.message
                assert result.platform == "zhihu"

    @pytest.mark.asyncio
    async def test_publish_missing_title(self, publisher, sample_article):
        """Given article missing title, when publish, then return PublishResult with failed."""
        sample_article["title"] = ""

        result = await publisher.publish(sample_article)

        assert isinstance(result, PublishResult)
        assert result.status == "failed"
        assert "title is required" in result.message.lower()
        assert result.platform == "zhihu"

    @pytest.mark.asyncio
    async def test_publish_missing_content(self, publisher, sample_article):
        """Given article missing content, when publish, then return PublishResult with failed."""
        sample_article["content"] = ""

        result = await publisher.publish(sample_article)

        assert isinstance(result, PublishResult)
        assert result.status == "failed"
        assert "content is required" in result.message.lower()
        assert result.platform == "zhihu"

    @pytest.mark.asyncio
    async def test_publish_network_error(self, publisher, sample_article, mock_access_token):
        """Given network error during publish, when publish, then return PublishResult with failed."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch("httpx.AsyncClient.post") as mock_post:
                import httpx
                mock_post.side_effect = httpx.ConnectError("Network error")

                result = await publisher.publish(sample_article)

                assert isinstance(result, PublishResult)
                assert result.status == "failed"
                assert "Network error" in result.message
                assert result.platform == "zhihu"

    @pytest.mark.asyncio
    async def test_publish_with_tags(self, publisher, sample_article, mock_access_token):
        """Given article with tags, when publish, then tags included in request."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "article_id": "1234567890123456789",
                    "url": "https://zhuanlan.zhihu.com/p/1234567890123456789"
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                result = await publisher.publish(sample_article)

                # Verify tags were included in the request
                call_args = mock_post.call_args
                request_data = call_args[1]["json"]
                assert "tags" in request_data
                assert request_data["tags"] == ["AI", "Technology"]

    @pytest.mark.asyncio
    async def test_publish_rate_limit(self, publisher, sample_article, mock_access_token):
        """Given API returns rate limit error, when publish, then return PublishResult with failed."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_response = Mock()
                mock_response.json.return_value = {
                    "error": "rate_limit_exceeded",
                    "error_description": "Rate limit exceeded. Please try again later."
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                result = await publisher.publish(sample_article)

                assert isinstance(result, PublishResult)
                assert result.status == "failed"
                assert "Rate limit exceeded" in result.message
                assert result.platform == "zhihu"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
