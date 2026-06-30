"""v1 采集器桥接模块测试 — 覆盖 7+ 平台映射"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.collect_bridge import (
    _COLLECTOR_MAP,
    get_available_sources,
    collect_from_source,
    collect_all,
)


class FakeCollector:
    """模拟 v1 采集器"""
    SOURCE_NAME = "test"

    def __init__(self, proxy=None, config=None):
        self.proxy = proxy
        self.config = config or {}

    async def collect(self, **kwargs) -> "FakeResult":
        return FakeResult(
            success=True,
            data=[
                {
                    "title": f"Test Article from {self.SOURCE_NAME}",
                    "content": "Test content body",
                    "url": f"https://example.com/{self.SOURCE_NAME}/1",
                    "published_at": "2026-06-30T00:00:00Z",
                }
            ],
            collected_count=1,
            skipped_count=0,
            duration=0.5,
        )


class FakeResult:
    def __init__(self, success, data, collected_count, skipped_count, duration, source_name="test", error=None):
        self.success = success
        self.data = data
        self.source_name = source_name
        self.collected_count = collected_count
        self.skipped_count = skipped_count
        self.duration = duration
        self.error = error


class FakeCollectorWeibo:
    SOURCE_NAME = "weibo_hot"
    def __init__(self, proxy=None, config=None):
        self.proxy = proxy
        self.config = config or {}
    async def collect(self, **kwargs) -> FakeResult:
        return FakeResult(
            success=True,
            data=[{"title": "微博热榜", "content": "热榜内容", "url": "https://weibo.com/hot"}],
            collected_count=1,
            skipped_count=0,
            duration=0.3,
        )


class FakeCollectorFail:
    SOURCE_NAME = "broken"
    def __init__(self, proxy=None, config=None):
        self.proxy = proxy
        self.config = config or {}
    async def collect(self, **kwargs) -> FakeResult:
        return FakeResult(
            success=False,
            data=[],
            collected_count=0,
            skipped_count=1,
            duration=0.1,
            error="Network error: connection refused",
        )


def _setup_bridge():
    """Inject fake collectors into the bridge's _COLLECTOR_MAP"""
    import app.services.collect_bridge as bridge

    bridge._COLLECTOR_MAP = {
        "youtube": FakeCollector,
        "wechat": FakeCollector,
        "douyin": FakeCollector,
        "weibo_hot": FakeCollectorWeibo,
        "twitter": FakeCollector,
        "rss": FakeCollector,
        "last30days": FakeCollector,
    }


class TestCollectBridge:
    """v1 → v2 桥接模块测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        _setup_bridge()

    @pytest.mark.asyncio
    async def test_get_available_sources(self):
        """get_available_sources 应返回所有已加载的采集源"""
        sources = get_available_sources()
        assert len(sources) == 7
        assert "youtube" in sources
        assert "wechat" in sources
        assert "douyin" in sources
        assert "weibo_hot" in sources
        assert "twitter" in sources
        assert "rss" in sources
        assert "last30days" in sources

    @pytest.mark.asyncio
    async def test_collect_from_source_simple(self):
        """collect_from_source 应返回文章列表"""
        articles = await collect_from_source("youtube", keyword="AI")
        assert articles is not None
        assert len(articles) == 1
        assert articles[0]["title"] == "Test Article from test"
        assert "content" in articles[0]
        assert "url" in articles[0]

    @pytest.mark.asyncio
    async def test_collect_from_source_weibo_hot(self):
        """微博热榜采集应返回特定格式数据"""
        articles = await collect_from_source("weibo_hot")
        assert articles is not None
        assert len(articles) == 1
        assert articles[0]["title"] == "微博热榜"
        assert articles[0]["url"] == "https://weibo.com/hot"

    @pytest.mark.asyncio
    async def test_collect_from_source_unknown(self):
        """未知采集源应返回 None"""
        articles = await collect_from_source("nonexistent_platform")
        assert articles is None

    @pytest.mark.asyncio
    async def test_collect_all(self):
        """collect_all 应并行执行所有采集器并返回完整映射"""
        results = await collect_all()
        assert isinstance(results, dict)
        assert len(results) == 7
        # 所有采集器应返回数据
        for name, articles in results.items():
            assert articles is not None, f"{name} 返回 None"
            assert len(articles) >= 1

    @pytest.mark.asyncio
    async def test_collect_all_with_empty_map(self):
        """当 _COLLECTOR_MAP 为空时 collect_all 应返回空字典"""
        import app.services.collect_bridge as bridge

        original = bridge._COLLECTOR_MAP
        bridge._COLLECTOR_MAP = {}
        try:
            results = await collect_all()
            assert results == {}
        finally:
            bridge._COLLECTOR_MAP = original

    @pytest.mark.asyncio
    async def test_collect_from_source_with_proxy(self):
        """采集器应接收 proxy 参数"""
        import app.services.collect_bridge as bridge

        original_map = bridge._COLLECTOR_MAP
        bridge._COLLECTOR_MAP = {"test": FakeCollector}
        try:
            articles = await collect_from_source("test", proxy="http://127.0.0.1:7890")
            assert articles is not None
        finally:
            bridge._COLLECTOR_MAP = original_map

    @pytest.mark.asyncio
    async def test_collect_on_empty_map(self):
        """当 _COLLECTOR_MAP 为空时 collect_from_source 应返回 None"""
        import app.services.collect_bridge as bridge

        original = bridge._COLLECTOR_MAP
        bridge._COLLECTOR_MAP = {}
        try:
            result = await collect_from_source("youtube")
            assert result is None
        finally:
            bridge._COLLECTOR_MAP = original
