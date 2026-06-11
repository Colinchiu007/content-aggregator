"""
Tests for WeChat publisher.

Following TDD workflow:
1. Write tests first (this file)
2. Run tests (they should fail)
3. Write code to make tests pass
4. Run tests (they should pass)
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import the publisher class
from content_aggregator.publishers.wechat import WechatPublisher, WechatAPIError
from content_aggregator.models.publish import PublishResult


class TestWechatPublisher:
    """Test cases for WeChatPublisher."""

    @pytest.fixture
    def publisher(self):
        """Create WechatPublisher instance with mock credentials."""
        return WechatPublisher(
            app_id="wx1234567890abcdef",
            app_secret="test_secret_12345"
        )

    @pytest.fixture
    def sample_article(self):
        """Sample article for testing."""
        return {
            "id": 123,
            "title": "Test Article Title",
            "content": "<p>This is test content.</p>",
            "summary": "Test summary",
            "cover_image": "/path/to/cover.jpg",
            "author": "Test Author"
        }

    @pytest.fixture
    def mock_access_token(self):
        """Mock access token response."""
        return {
            "access_token": "mock_access_token_12345",
            "expires_in": 7200
        }

    # ===== Test Cases for __init__ =====

    def test_init_success(self, publisher):
        """Given valid credentials, when init, then set app_id and app_secret."""
        assert publisher.app_id == "wx1234567890abcdef"
        assert publisher.app_secret == "test_secret_12345"
        assert publisher.access_token is None
        assert publisher.token_expires_at == 0

    def test_init_empty_app_id(self):
        """Given empty app_id, when init, then raise ValueError."""
        with pytest.raises(ValueError, match="app_id cannot be empty"):
            WechatPublisher(app_id="", app_secret="test_secret")

    def test_init_empty_app_secret(self):
        """Given empty app_secret, when init, then raise ValueError."""
        with pytest.raises(ValueError, match="app_secret cannot be empty"):
            WechatPublisher(app_id="wx123456", app_secret="")

    # ===== Test Cases for get_access_token() ======

    @pytest.mark.asyncio
    async def test_get_access_token_success(self, publisher, mock_access_token):
        """Given valid credentials, when get_access_token, then return token."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_access_token
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            token = await publisher.get_access_token()

            assert token == "mock_access_token_12345"
            assert publisher.access_token == "mock_access_token_12345"
            assert publisher.token_expires_at > 0

    @pytest.mark.asyncio
    async def test_get_access_token_api_error(self, publisher):
        """Given API returns error, when get_access_token, then raise WechatAPIError."""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {
                "errcode": 40013,
                "errmsg": "invalid appid"
            }
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            with pytest.raises(WechatAPIError, match="invalid appid"):
                await publisher.get_access_token()

    @pytest.mark.asyncio
    async def test_get_access_token_network_error(self, publisher):
        """Given network error, when get_access_token, then raise WechatAPIError."""
        with patch("httpx.AsyncClient.get") as mock_get:
            # Raise httpx.RequestError (not generic Exception)
            import httpx
            mock_get.side_effect = httpx.ConnectError("Network error")

            with pytest.raises(WechatAPIError, match="Failed to get access token"):
                await publisher.get_access_token()

    @pytest.mark.asyncio
    async def test_get_access_token_cached(self, publisher, mock_access_token):
        """Given token already cached and not expired, when get_access_token, then return cached token."""
        # Set cached token
        publisher.access_token = "cached_token"
        publisher.token_expires_at = datetime.now().timestamp() + 3600

        with patch("httpx.AsyncClient.get") as mock_get:
            token = await publisher.get_access_token()

            assert token == "cached_token"
            mock_get.assert_not_called()  # Should not call API

    # ===== Test Cases for upload_media() ======

    @pytest.mark.asyncio
    async def test_upload_media_success(self, publisher, sample_article, mock_access_token):
        """Given valid image, when upload_media, then return media_id."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            # Mock file exists check
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value = MagicMock()
                    with patch("httpx.AsyncClient.post") as mock_post:
                        mock_response = Mock()
                        mock_response.json.return_value = {
                            "media_id": "mock_media_id_12345",
                            "url": "https://mmbiz.qpic.cn/..."
                        }
                        mock_response.raise_for_status.return_value = None
                        mock_post.return_value = mock_response

                        media_id = await publisher.upload_media(sample_article["cover_image"])

                        assert media_id == "mock_media_id_12345"

    @pytest.mark.asyncio
    async def test_upload_media_file_not_found(self, publisher):
        """Given file not found, when upload_media, then raise WechatAPIError."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            # Mock file not exists
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(WechatAPIError, match="File not found"):
                    await publisher.upload_media("/path/to/nonexistent.jpg")

    @pytest.mark.asyncio
    async def test_upload_media_api_error(self, publisher, sample_article, mock_access_token):
        """Given API returns error, when upload_media, then raise WechatAPIError."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            # Mock file exists check
            with patch("pathlib.Path.exists", return_value=True):
                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value = MagicMock()
                    with patch("httpx.AsyncClient.post") as mock_post:
                        mock_response = Mock()
                        mock_response.json.return_value = {
                            "errcode": 40004,
                            "errmsg": "invalid media type"
                        }
                        mock_response.raise_for_status.return_value = None
                        mock_post.return_value = mock_response
                        
                        with pytest.raises(WechatAPIError, match="invalid media type"):
                            await publisher.upload_media(sample_article["cover_image"])

    # ===== Test Cases for create_draft() ======

    @pytest.mark.asyncio
    async def test_create_draft_success(self, publisher, sample_article, mock_access_token):
        """Given valid article, when create_draft, then return media_id."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch.object(publisher, "upload_media", return_value="mock_media_id"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_response = Mock()
                    mock_response.json.return_value = {
                        "media_id": "mock_draft_media_id"
                    }
                    mock_response.raise_for_status.return_value = None
                    mock_post.return_value = mock_response

                    media_id = await publisher.create_draft(sample_article)

                    assert media_id == "mock_draft_media_id"

    @pytest.mark.asyncio
    async def test_create_draft_api_error(self, publisher, sample_article, mock_access_token):
        """Given API returns error, when create_draft, then raise WechatAPIError."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch.object(publisher, "upload_media", return_value="mock_media_id"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_response = Mock()
                    mock_response.json.return_value = {
                        "errcode": 88000,
                        "errmsg": "content contains sensitive words"
                    }
                    mock_response.raise_for_status.return_value = None
                    mock_post.return_value = mock_response

                    with pytest.raises(WechatAPIError, match="content contains sensitive words"):
                        await publisher.create_draft(sample_article)

    # ===== Test Cases for publish() ======

    @pytest.mark.asyncio
    async def test_publish_success(self, publisher, sample_article, mock_access_token):
        """Given valid article, when publish, then return PublishResult with success."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch.object(publisher, "create_draft", return_value="mock_media_id"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_response = Mock()
                    mock_response.json.return_value = {
                        "publish_id": "mock_publish_id",
                        "msg_data_id": "mock_msg_data_id"
                    }
                    mock_response.raise_for_status.return_value = None
                    mock_post.return_value = mock_response

                    result = await publisher.publish(sample_article)

                    assert isinstance(result, PublishResult)
                    assert result.status == "success"
                    assert result.url == f"https://mp.weixin.qq.com/s/{mock_response.json()['msg_data_id']}"

    @pytest.mark.asyncio
    async def test_publish_draft_creation_fails(self, publisher, sample_article, mock_access_token):
        """Given draft creation fails, when publish, then return PublishResult with failed."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch.object(publisher, "create_draft", side_effect=WechatAPIError("Draft creation failed")):
                result = await publisher.publish(sample_article)

                assert isinstance(result, PublishResult)
                assert result.status == "failed"
                assert "Draft creation failed" in result.message

    @pytest.mark.asyncio
    async def test_publish_api_error(self, publisher, sample_article, mock_access_token):
        """Given API returns error, when publish, then return PublishResult with failed."""
        with patch.object(publisher, "get_access_token", return_value="mock_token"):
            with patch.object(publisher, "create_draft", return_value="mock_media_id"):
                with patch("httpx.AsyncClient.post") as mock_post:
                    mock_response = Mock()
                    mock_response.json.return_value = {
                        "errcode": 88000,
                        "errmsg": "content contains sensitive words"
                    }
                    mock_response.raise_for_status.return_value = None
                    mock_post.return_value = mock_response

                    result = await publisher.publish(sample_article)

                    assert isinstance(result, PublishResult)
                    assert result.status == "failed"
                    assert "content contains sensitive words" in result.message

    @pytest.mark.asyncio
    async def test_publish_missing_cover_image(self, publisher, sample_article, mock_access_token):
        """Given article missing cover image, when publish, then return PublishResult with failed."""
        sample_article["cover_image"] = None

        result = await publisher.publish(sample_article)

        assert isinstance(result, PublishResult)
        assert result.status == "failed"
        assert "cover image is required" in result.message.lower()

    @pytest.mark.asyncio
    async def test_publish_missing_title(self, publisher, sample_article, mock_access_token):
        """Given article missing title, when publish, then return PublishResult with failed."""
        sample_article["title"] = ""

        result = await publisher.publish(sample_article)

        assert isinstance(result, PublishResult)
        assert result.status == "failed"
        assert "title is required" in result.message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
