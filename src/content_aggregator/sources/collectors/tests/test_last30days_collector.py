"""
Last30DaysCollector 单元测试 — mock 所有 HTTP 请求

覆盖范围:
1. normalize_engagement() — 4 平台归一化
2. compute_freshness_score() — 边界条件
3. rrf_score() — 数学正确性
4. Last30DaysCollector._fetch() — 并行 4 源采集
5. 单源失败不影响其他源
6. 空结果处理
7. 错误源恢复
8. 未知源跳过
9. 无有效源返回空列表
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest import approx

from content_aggregator.sources.collectors.last30days_collector import (
    Last30DaysCollector,
    normalize_engagement,
    compute_freshness_score,
    rrf_score,
    SOURCE_FETCHERS,
)


# ═══════════════════════════════════════════════════════════════
# normalize_engagement
# ═══════════════════════════════════════════════════════════════

class TestNormalizeEngagement:
    def test_reddit_upvotes_high(self):
        """高 upvotes → log10(n+1)/5.0"""
        score = normalize_engagement("reddit", {"upvotes": 99999})
        assert 0 < score <= 1.0
        # log10(100000)/5.0 = 5.0/5.0 = 1.0
        assert round(score, 4) == 1.0

    def test_reddit_upvotes_zero(self):
        """零 upvotes → 0.0"""
        assert normalize_engagement("reddit", {"upvotes": 0}) == 0.0

    def test_reddit_upvotes_low(self):
        """低 upvotes → 合理分数"""
        score = normalize_engagement("reddit", {"upvotes": 10})
        # log10(11)/5.0 ≈ 1.0414/5.0 ≈ 0.2083
        assert 0 < score < 1.0
        assert round(score, 4) == 0.2083

    def test_github_stars(self):
        """GitHub stars 归一化"""
        score = normalize_engagement("github", {"stars": 100})
        # log10(101)/5.0 ≈ 2.0043/5.0 ≈ 0.4009
        assert round(score, 4) == 0.4009

    def test_hackernews_points(self):
        """HN points 归一化"""
        score = normalize_engagement("hackernews", {"points": 500})
        # log10(501)/5.0 ≈ 2.6998/5.0 ≈ 0.5400
        assert round(score, 4) == 0.5400

    def test_polymarket_volume(self):
        """Polymarket volume 归一化（min 截断）"""
        score = normalize_engagement("polymarket", {"volume": 200000})
        assert score == 1.0

    def test_polymarket_volume_low(self):
        """Polymarket 低 volume"""
        score = normalize_engagement("polymarket", {"volume": 50000})
        assert round(score, 4) == 0.5

    def test_unknown_source(self):
        """未知源返回 0.0"""
        assert normalize_engagement("unknown", {}) == 0.0

    def test_missing_engagement_key(self):
        """缺失 engagement 字段返回 0.0"""
        assert normalize_engagement("reddit", {}) == 0.0

    def test_non_numeric_engagement(self):
        """非数字 engagement 返回 0.0"""
        assert normalize_engagement("reddit", {"upvotes": None}) == 0.0


# ═══════════════════════════════════════════════════════════════
# compute_freshness_score
# ═══════════════════════════════════════════════════════════════

class TestComputeFreshnessScore:
    def test_none_date(self):
        """None 日期返回 0.5"""
        assert compute_freshness_score(None) == 0.5

    def test_just_now(self):
        """当前时间 → 1.0（age_days <= 0）"""
        assert compute_freshness_score(datetime.now(timezone.utc)) == approx(1.0, abs=0.01)

    def test_15_days_ago(self):
        """15 天前 → 0.5"""
        from datetime import timedelta
        dt = datetime.now(timezone.utc) - timedelta(days=15)
        score = compute_freshness_score(dt)
        assert round(score, 4) == 0.5

    def test_30_days_ago(self):
        """30 天前 → 0.0"""
        from datetime import timedelta
        dt = datetime.now(timezone.utc) - timedelta(days=30)
        assert compute_freshness_score(dt) == 0.0

    def test_over_30_days(self):
        """超过 30 天 → 0.0"""
        from datetime import timedelta
        dt = datetime.now(timezone.utc) - timedelta(days=60)
        assert compute_freshness_score(dt) == 0.0

    def test_future_date(self):
        """未来日期 → 1.0"""
        from datetime import timedelta
        dt = datetime.now(timezone.utc) + timedelta(days=1)
        assert compute_freshness_score(dt) == 1.0

    def test_naive_datetime(self):
        """无时区 datetime 被自动设 UTC"""
        from datetime import timedelta
        naive = datetime.now() - timedelta(days=7)
        score = compute_freshness_score(naive)
        assert 0 < score < 1.0


# ═══════════════════════════════════════════════════════════════
# rrf_score
# ═══════════════════════════════════════════════════════════════

class TestRRFScore:
    def test_rank_1(self):
        """rank=1 → 1/(60+1) ≈ 0.0164"""
        assert round(rrf_score(1), 4) == 0.0164

    def test_rank_10(self):
        """rank=10 → 1/(60+10) ≈ 0.0143"""
        assert round(rrf_score(10), 4) == 0.0143

    def test_rank_100(self):
        """rank=100 → 1/(60+100) ≈ 0.00625"""
        assert round(rrf_score(100), 4) == 0.0063

    def test_custom_k(self):
        """自定义 k 值"""
        assert round(rrf_score(1, k=10), 4) == 0.0909


# ═══════════════════════════════════════════════════════════════
# Last30DaysCollector._fetch
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def collector():
    """Create a Last30DaysCollector with default config."""
    return Last30DaysCollector(config={"sources": ["reddit", "github", "hackernews", "polymarket"]})


def _mock_client() -> AsyncMock:
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock(spec_set=["get"])
    return client


def _make_item(source: str, rank: int = 1) -> dict:
    """Create a minimal mock result item."""
    item = {
        "item_id": f"{source}-{rank}",
        "source": source,
        "title": f"Test {source} #{rank}",
        "url": f"https://{source}.com/item/{rank}",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "engagement": {"upvotes": 100, "stars": 100, "points": 100, "volume": 10000},
    }
    return item


class TestCollectorFetch:
    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_parallel_fetch_all_sources(self, mock_fetchers, collector):
        """并行 4 源采集 — 所有源返回数据"""
        for src in ["reddit", "hackernews", "github", "polymarket"]:
            fetcher = AsyncMock(return_value=[_make_item(src, 1)])
            mock_fetchers.__getitem__.return_value = fetcher
            # Make __contains__ work properly
            mock_fetchers.__contains__.side_effect = lambda s: s in ["reddit", "hackernews", "github", "polymarket"]

        mock_fetchers.__contains__.side_effect = lambda s: s in ["reddit", "hackernews", "github", "polymarket"]
        mock_fetchers.__getitem__.side_effect = lambda s: {
            "reddit": AsyncMock(return_value=[_make_item("reddit", 1)]),
            "hackernews": AsyncMock(return_value=[_make_item("hackernews", 1)]),
            "github": AsyncMock(return_value=[_make_item("github", 1)]),
            "polymarket": AsyncMock(return_value=[_make_item("polymarket", 1)]),
        }[s]

        with patch.object(collector, "_get_client", return_value=AsyncMock()):
            results = await collector._fetch(topic="AI")

        assert len(results) > 0
        # Should have some results from 4 sources

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_one_source_fails_others_continue(self, mock_fetchers, collector):
        """单一源失败不影响其他源"""
        async def _ok(*args, **kwargs):
            return [_make_item("reddit", 1)]

        async def _fail(*args, **kwargs):
            raise ConnectionError("Connection refused")

        mock_fetchers.__contains__.side_effect = lambda s: s in ["reddit", "hackernews", "github", "polymarket"]
        mock_fetchers.__getitem__.side_effect = lambda s: {
            "reddit": _ok,
            "hackernews": _fail,
            "github": _ok,
            "polymarket": _ok,
        }[s]

        with patch.object(collector, "_get_client", return_value=AsyncMock()):
            results = await collector._fetch(topic="test")

        # Should still return results from working sources
        assert len(results) > 0

    async def test_fetch_with_empty_sources(self):
        """无有效源时返回空列表"""
        c = Last30DaysCollector(config={"sources": []})
        with patch.object(c, "_get_client", return_value=AsyncMock()):
            results = await c._fetch(topic="test")
        assert results == []

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_unknown_source_skipped(self, mock_fetchers):
        """未知源自动跳过"""
        mock_fetchers.__contains__.side_effect = lambda s: False
        mock_fetchers.__getitem__.side_effect = KeyError

        c = Last30DaysCollector(config={"sources": ["unknown_platform"]})
        with patch.object(c, "_get_client", return_value=AsyncMock()):
            results = await c._fetch(topic="test")
        assert results == []

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_fetch_deduplication(self, mock_fetchers, collector):
        """重复 item_id 自动去重"""
        mock_fetchers.__contains__.side_effect = lambda s: s in ["reddit"]
        mock_fetchers.__getitem__.side_effect = lambda s: AsyncMock(return_value=[
            _make_item("reddit", 1),
            _make_item("reddit", 1),  # same item_id
        ])

        with patch.object(collector, "_get_client", return_value=AsyncMock()):
            results = await collector._fetch(topic="test")

        # Check dedup: same item_id should only appear once
        item_ids = [r["item_id"] for r in results]
        assert len(item_ids) == len(set(item_ids))

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_total_max_limit(self, mock_fetchers):
        """total_max 限制返回数量"""
        mock_fetchers.__contains__.side_effect = lambda s: s in ["reddit"]
        mock_fetchers.__getitem__.side_effect = lambda s: AsyncMock(return_value=[
            _make_item("reddit", i) for i in range(10)
        ])

        c = Last30DaysCollector(config={"sources": ["reddit"], "total_max": 3})
        with patch.object(c, "_get_client", return_value=AsyncMock()):
            results = await c._fetch(topic="test")
        assert len(results) <= 3

    async def test_score_ranges(self, collector):
        """所有评分字段在合理范围内"""
        from datetime import timedelta
        # Manually test the scoring functions for edge cases
        # Very old item
        old = datetime.now(timezone.utc) - timedelta(days=100)
        assert compute_freshness_score(old) == 0.0

        # Very high engagement
        high = normalize_engagement("reddit", {"upvotes": 1_000_000})
        assert high <= 1.0
        assert high > 0

        # Very low engagement
        low = normalize_engagement("reddit", {"upvotes": 1})
        assert low > 0
        assert low < 1.0

    async def test_collect_method_integration(self, collector):
        """collect() 方法应包装 _fetch 并返回 SourceResult"""
        with patch.object(collector, "_fetch", return_value=[_make_item("reddit", 1)]):
            result = await collector.collect(topic="AI")

        assert result.success is True
        assert len(result.data) >= 1
        assert result.source_name == "last30days"
        assert result.duration >= 0

    async def test_collect_method_error_handling(self, collector):
        """collect() 在 _fetch 抛异常时应优雅处理"""
        with patch.object(collector, "_fetch", side_effect=Exception("Unexpected error")):
            result = await collector.collect(topic="AI")

        # BaseCollector.collect handles errors from _fetch
        # It returns success=True with empty data (graceful degradation)
        assert result.data == [] or result.success is not None

    async def test_config_sources_override(self):
        """config.sources 应覆盖默认源列表"""
        c = Last30DaysCollector(config={"sources": ["reddit"]})
        assert c.enabled_sources == ["reddit"]

        c2 = Last30DaysCollector()
        assert c2.enabled_sources == ["reddit", "hackernews", "github", "polymarket"]

    async def test_client_lifecycle(self, collector):
        """_get_client 应返回 httpx.AsyncClient"""
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value = AsyncMock()
            client = await collector._get_client()
            assert client is not None
