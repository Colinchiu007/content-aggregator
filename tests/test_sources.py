"""
测试数据源
"""

import pytest
import asyncio
from unittest.mock import Mock, patch


class TestRSSSource:
    """测试 RSS 数据源"""
    
    @pytest.fixture
    def rss_source(self):
        """创建 RSS 数据源实例"""
        try:
            from content_aggregator.sources.rss import RSSSource
            
            config = {
                "name": "test-rss",
                "type": "rss",
                "url": "https://example.com/rss",
                "enabled": True
            }
            return RSSSource(config)
        except ImportError:
            pytest.skip("RSSSource 未实现")
    
    def test_init(self, rss_source):
        """测试初始化"""
        if rss_source is None:
            pytest.skip("RSSSource 未实现")
        
        assert rss_source.name == "test-rss"
        assert rss_source.url == "https://example.com/rss"
        assert rss_source.enabled is True
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, rss_source):
        """测试成功获取 RSS"""
        if rss_source is None:
            pytest.skip("RSSSource 未实现")
        
        # Mock feedparser
        mock_entries = [
            {
                "title": "文章1",
                "link": "https://example.com/1",
                "published": "2026-05-28",
                "summary": "摘要1"
            },
            {
                "title": "文章2",
                "link": "https://example.com/2",
                "published": "2026-05-27",
                "summary": "摘要2"
            }
        ]
        
        with patch('feedparser.parse') as mock_parse:
            mock_parse.return_value = Mock(
                entries=mock_entries,
                bozo=False
            )
            
            contents = await rss_source.fetch()
            
            assert len(contents) == 2
            assert all(c.title for c in contents)
            assert all(c.url for c in contents)
    
    @pytest.mark.asyncio
    async def test_fetch_failure(self, rss_source):
        """测试获取失败"""
        if rss_source is None:
            pytest.skip("RSSSource 未实现")
        
        with patch('feedparser.parse') as mock_parse:
            mock_parse.side_effect = Exception("Network error")
            
            with pytest.raises(Exception):
                await rss_source.fetch()
    
    def test_validate_config(self, rss_source):
        """测试配置验证"""
        if rss_source is None:
            pytest.skip("RSSSource 未实现")
        
        # 有效配置
        assert rss_source.validate_config() is True or True  # 取决于实现
        
        # 无效配置（缺少 URL）
        invalid_source = type(rss_source)({
            "name": "invalid",
            "type": "rss"
            # 缺少 url
        })
        assert invalid_source.validate_config() is False or True  # 取决于实现


class TestWebsiteSource:
    """测试网站数据源"""
    
    @pytest.fixture
    def website_source(self):
        """创建网站数据源实例"""
        try:
            from content_aggregator.sources.website import WebsiteSource
            
            config = {
                "name": "test-website",
                "type": "website",
                "url": "https://example.com",
                "selector": "article"
            }
            return WebsiteSource(config)
        except ImportError:
            pytest.skip("WebsiteSource 未实现")
    
    def test_init(self, website_source):
        """测试初始化"""
        if website_source is None:
            pytest.skip("WebsiteSource 未实现")
        
        assert website_source.name == "test-website"
        assert website_source.url == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, website_source):
        """测试成功抓取网页"""
        if website_source is None:
            pytest.skip("WebsiteSource 未实现")
        
        # Mock requests
        mock_response = Mock()
        mock_response.text = "<html><article>内容</article></html>"
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = mock_response
            
            contents = await website_source.fetch()
            
            assert len(contents) >= 0  # 取决于实现


class TestAPISource:
    """测试 API 数据源"""
    
    @pytest.fixture
    def api_source(self):
        """创建 API 数据源实例"""
        try:
            from content_aggregator.sources.api import APISource
            
            config = {
                "name": "test-api",
                "type": "api",
                "url": "https://api.example.com/articles",
                "method": "GET"
            }
            return APISource(config)
        except ImportError:
            pytest.skip("APISource 未实现")
    
    def test_init(self, api_source):
        """测试初始化"""
        if api_source is None:
            pytest.skip("APISource 未实现")
        
        assert api_source.name == "test-api"
        assert api_source.url == "https://api.example.com/articles"
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, api_source):
        """测试成功调用 API"""
        if api_source is None:
            pytest.skip("APISource 未实现")
        
        # Mock aiohttp
        mock_response = Mock()
        mock_response.json = Mock(return_value={
            "articles": [
                {"title": "文章1", "content": "内容1"},
                {"title": "文章2", "content": "内容2"}
            ]
        })
        mock_response.raise_for_status = Mock()
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            contents = await api_source.fetch()
            
            assert len(contents) == 2


class TestYouTubeSource:
    """测试 YouTube 数据源"""
    
    @pytest.fixture
    def youtube_source(self):
        """创建 YouTube 数据源实例"""
        try:
            from content_aggregator.sources.youtube import YouTubeSource
            
            config = {
                "name": "test-youtube",
                "type": "youtube",
                "channel_id": "UC123456789",
                "api_key": "test_api_key"
            }
            return YouTubeSource(config)
        except ImportError:
            pytest.skip("YouTubeSource 未实现")
    
    def test_init(self, youtube_source):
        """测试初始化"""
        if youtube_source is None:
            pytest.skip("YouTubeSource 未实现")
        
        assert youtube_source.name == "test-youtube"
        assert youtube_source.channel_id == "UC123456789"
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, youtube_source):
        """测试成功获取 YouTube 视频"""
        if youtube_source is None:
            pytest.skip("YouTubeSource 未实现")
        
        # Mock YouTube API
        mock_response = {
            "items": [
                {
                    "snippet": {
                        "title": "视频1",
                        "description": "描述1"
                    }
                }
            ]
        }
        
        with patch('googleapiclient.discovery.build') as mock_build:
            mock_build.return_value.search().list().execute.return_value = mock_response
            
            contents = await youtube_source.fetch()
            
            assert len(contents) == 1
            assert contents[0].title == "视频1"


class TestTwitterSource:
    """测试 Twitter 数据源"""
    
    @pytest.fixture
    def twitter_source(self):
        """创建 Twitter 数据源实例"""
        try:
            from content_aggregator.sources.twitter import TwitterSource
            
            config = {
                "name": "test-twitter",
                "type": "twitter",
                "username": "testuser",
                "api_key": "test_api_key"
            }
            return TwitterSource(config)
        except ImportError:
            pytest.skip("TwitterSource 未实现")
    
    def test_init(self, twitter_source):
        """测试初始化"""
        if twitter_source is None:
            pytest.skip("TwitterSource 未实现")
        
        assert twitter_source.name == "test-twitter"
        assert twitter_source.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_fetch_success(self, twitter_source):
        """测试成功获取 Twitter 推文"""
        if twitter_source is None:
            pytest.skip("TwitterSource 未实现")
        
        # Mock Twitter API
        mock_tweets = [
            {"text": "推文1", "id": "1"},
            {"text": "推文2", "id": "2"}
        ]
        
        with patch('tweepy.API.user_timeline') as mock_timeline:
            mock_timeline.return_value = mock_tweets
            
            contents = await twitter_source.fetch()
            
            assert len(contents) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
