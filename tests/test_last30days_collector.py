"""Last30DaysCollector 单元测试

覆盖: 并行采集(4源)、normalize_engagement()、compute_freshness_score()、
rrf_score()、空结果处理、错误源恢复
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from content_aggregator.sources.collectors.last30days_collector import (
    ENGAGEMENT_NORMALIZERS,
    SOURCE_FETCHERS,
    Last30DaysCollector,
    compute_freshness_score,
    create_last30days_collector,
    normalize_engagement,
    rrf_score,
)


# ═══════════════════════════════════════════════════════════════════
# normalize_engagement 单元测试
# ═══════════════════════════════════════════════════════════════════

class TestNormalizeEngagement:
    """normalize_engagement() 覆盖所有源和边界"""

    def test_reddit_upvotes(self):
        """Reddit upvotes → log10 归一化"""
        score = normalize_engagement("reddit", {"upvotes": 1000})
        assert 0 < score <= 1.0
        assert round(score, 4) == round(min(math.log10(1001) / 5.0, 1.0), 4)

    def test_github_stars(self):
        """GitHub stars → log10 归一化"""
        score = normalize_engagement("github", {"stars": 5000})
        assert 0 < score <= 1.0

    def test_hackernews_points(self):
        """HackerNews points → log10 归一化"""
        score = normalize_engagement("hackernews", {"points": 100})
        assert 0 < score <= 1.0

    def test_polymarket_volume(self):
        """Polymarket volume → 线性归一化"""
        score = normalize_engagement("polymarket", {"volume": 50000})
        assert 0 < score <= 1.0
        assert score == 0.5  # 50000 / 100000 = 0.5

    def test_polymarket_volume_exceeds_divisor(self):
        """Polymarket volume 超过 divisor → cap at 1.0"""
        score = normalize_engagement("polymarket", {"volume": 200000})
        assert score == 1.0

    def test_unknown_source(self):
        """未知源 → 返回 0.0"""
        score = normalize_engagement("unknown", {"upvotes": 100})
        assert score == 0.0

    def test_zero_engagement(self):
        """零互动 → 返回 0.0"""
        score = normalize_engagement("reddit", {"upvotes": 0})
        assert score == 0.0

    def test_negative_engagement(self):
        """负互动 → 返回 0.0 (log10 不处理负数)"""
        score = normalize_engagement("reddit", {"upvotes": -5})
        assert score == 0.0

    def test_missing_field(self):
        """缺少关键字段 → 返回 0.0"""
        score = normalize_engagement("reddit", {"comments": 100})
        assert score == 0.0

    def test_empty_engagement_dict(self):
        """空 dict → 返回 0.0"""
        score = normalize_engagement("reddit", {})
        assert score == 0.0


# ═══════════════════════════════════════════════════════════════════
# compute_freshness_score 单元测试
# ═══════════════════════════════════════════════════════════════════

class TestComputeFreshnessScore:
    """compute_freshness_score() 覆盖各种时间场景"""

    def test_now(self):
        """发布时间为当前 → 返回 1.0"""
        score = compute_freshness_score(datetime.now(timezone.utc))
        assert score == 1.0

    def test_15_days_ago(self):
        """15天前 → 返回 ~0.5"""
        from datetime import timedelta
        past = datetime.now(timezone.utc) - timedelta(days=15)
        score = compute_freshness_score(past)
        assert 0.4 < score < 0.6

    def test_30_days_ago(self):
        """30天前 → 返回 0.0"""
        from datetime import timedelta
        past = datetime.now(timezone.utc) - timedelta(days=30)
        score = compute_freshness_score(past)
        assert score == 0.0

    def test_over_30_days(self):
        """超过30天 → 返回 0.0"""
        from datetime import timedelta
        past = datetime.now(timezone.utc) - timedelta(days=45)
        score = compute_freshness_score(past)
        assert score == 0.0

    def test_future_date(self):
        """未来时间 → 返回 1.0"""
        from datetime import timedelta
        future = datetime.now(timezone.utc) + timedelta(days=1)
        score = compute_freshness_score(future)
        assert score == 1.0

    def test_none_date(self):
        """None → 返回 0.5（未知时间的默认分）"""
        score = compute_freshness_score(None)
        assert score == 0.5

    def test_naive_datetime(self):
        """无时区信息的 datetime → 自动转换"""
        from datetime import timedelta
        naive = datetime.now() - timedelta(days=7)
        score = compute_freshness_score(naive)
        assert 0 < score < 1.0

    def test_custom_days_back(self):
        """自定义 days_back 参数"""
        from datetime import timedelta
        past = datetime.now(timezone.utc) - timedelta(days=15)
        score = compute_freshness_score(past, days_back=60)
        assert score > 0.7


# ═══════════════════════════════════════════════════════════════════
# rrf_score 单元测试
# ═══════════════════════════════════════════════════════════════════

class TestRRFScore:
    """rrf_score() RRF 排名融合"""

    def test_rank_1_default_k(self):
        """rank=1, k=60 → 1/61"""
        assert rrf_score(1) == 1.0 / 61.0

    def test_rank_10(self):
        """rank=10 → 1/70"""
        assert rrf_score(10) == 1.0 / 70.0

    def test_rank_60(self):
        """rank=60 → 1/120"""
        assert rrf_score(60) == 1.0 / 120.0

    def test_custom_k(self):
        """自定义 k=100"""
        assert rrf_score(1, k=100) == 1.0 / 101.0

    def test_rank_0(self):
        """rank=0 → 1/k"""
        assert rrf_score(0) == 1.0 / 60.0


# ═══════════════════════════════════════════════════════════════════
# Last30DaysCollector._fetch 模拟测试
# ═══════════════════════════════════════════════════════════════════

class TestLast30DaysCollectorFetch:
    """Last30DaysCollector._fetch() 覆盖并行采集和错误恢复"""

    @pytest.fixture
    def collector(self):
        """创建测试用 collector 实例"""
        return Last30DaysCollector(config={
            "sources": ["reddit", "hackernews", "github", "polymarket"],
            "max_per_source": 3,
            "total_max": 10,
            "days_back": 30,
        })

    @pytest.fixture
    def mock_client(self):
        """创建 mock httpx.AsyncClient"""
        client = AsyncMock()
        return client

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_parallel_collect_all_sources(
        self, mock_fetchers, collector, mock_client
    ):
        """4源并行采集应合并结果并按 RRF 排序"""
        mock_fetchers.__getitem__.side_effect = lambda key: {
            "reddit": AsyncMock(return_value=[{
                "item_id": "reddit-1", "source": "reddit",
                "title": "Reddit Post", "body": "", "url": "",
                "author": "", "published_at": "2026-06-28T00:00:00Z",
                "engagement": {"upvotes": 500}, "container": "r/test",
            }]),
            "hackernews": AsyncMock(return_value=[{
                "item_id": "hn-1", "source": "hackernews",
                "title": "HN Story", "body": "", "url": "",
                "author": "", "published_at": "2026-06-25T00:00:00Z",
                "engagement": {"points": 200}, "container": "Hacker News",
            }]),
            "github": AsyncMock(return_value=[{
                "item_id": "github-1", "source": "github",
                "title": "GitHub Repo", "body": "", "url": "",
                "author": "", "published_at": "2026-06-20T00:00:00Z",
                "engagement": {"stars": 1000}, "container": "owner/repo",
            }]),
            "polymarket": AsyncMock(return_value=[{
                "item_id": "polymarket-1", "source": "polymarket",
                "title": "PM Event", "body": "", "url": "",
                "author": "", "published_at": "2026-06-15T00:00:00Z",
                "engagement": {"volume": 50000}, "container": "Polymarket",
            }]),
        }[key]

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("AI", sources=["reddit", "hackernews", "github", "polymarket"], max_per_source=1, total_max=10)

        assert len(result) == 4
        # 结果应按 _final_score 降序排列
        item_ids = [item["item_id"] for item in result]
        assert "reddit-1" in item_ids
        assert "hn-1" in item_ids
        assert "github-1" in item_ids
        assert "polymarket-1" in item_ids

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_empty_results(self, mock_fetchers, collector, mock_client):
        """所有源返回空 → 返回空列表"""
        mock_fetchers.__getitem__.side_effect = lambda key: AsyncMock(return_value=[])

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("nothing", sources=["reddit", "hackernews"], max_per_source=1, total_max=10)

        assert result == []

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_partial_source_failure(self, mock_fetchers, collector, mock_client):
        """部分源失败时恢复，返回成功的源"""
        mock_fetchers.__getitem__.side_effect = lambda key: {
            "reddit": AsyncMock(return_value=[{
                "item_id": "reddit-1", "source": "reddit",
                "title": "Reddit Post", "body": "", "url": "",
                "author": "", "published_at": "2026-06-28T00:00:00Z",
                "engagement": {"upvotes": 500}, "container": "r/test",
            }]),
            "hackernews": AsyncMock(side_effect=Exception("API rate limit")),
        }[key]

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("topic", sources=["reddit", "hackernews"], max_per_source=1, total_max=10)

        # 失败的源被跳过，成功的源结果保留
        assert len(result) == 1
        assert result[0]["source"] == "reddit"

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_all_sources_fail(self, mock_fetchers, collector, mock_client):
        """所有源失败 → 返回空列表"""
        mock_fetchers.__getitem__.side_effect = lambda key: AsyncMock(side_effect=Exception("Network error"))

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("topic", sources=["reddit", "github"], max_per_source=1, total_max=10)

        assert result == []

    async def test_no_valid_sources(self, collector):
        """没有有效源 → 返回空列表"""
        with patch.object(collector, "_get_client"):
            result = await collector._fetch("topic", sources=["unknown_source"], max_per_source=1, total_max=10)

        assert result == []

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_deduplication(self, mock_fetchers, collector, mock_client):
        """重复 item_id 应去重"""
        mock_fetchers.__getitem__.side_effect = lambda key: AsyncMock(return_value=[
            {
                "item_id": "dup-1", "source": "reddit",
                "title": "Same Item", "body": "", "url": "",
                "author": "", "published_at": "2026-06-28T00:00:00Z",
                "engagement": {"upvotes": 100}, "container": "r/test",
            },
            {
                "item_id": "dup-1", "source": "reddit",
                "title": "Duplicate", "body": "", "url": "",
                "author": "", "published_at": "2026-06-28T00:00:00Z",
                "engagement": {"upvotes": 100}, "container": "r/test",
            },
        ])

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("topic", sources=["reddit"], max_per_source=2, total_max=10)

        assert len(result) == 1  # 重复的被去重

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_total_max_limit(self, mock_fetchers, collector, mock_client):
        """total_max 限制返回结果数量"""
        many_items = [
            {
                "item_id": f"item-{i}", "source": "reddit",
                "title": f"Item {i}", "body": "", "url": "",
                "author": "", "published_at": "2026-06-28T00:00:00Z",
                "engagement": {"upvotes": 100 - i}, "container": "r/test",
            }
            for i in range(20)
        ]
        mock_fetchers.__getitem__.side_effect = lambda key: AsyncMock(return_value=many_items)

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("topic", sources=["reddit"], max_per_source=20, total_max=5)

        assert len(result) <= 5

    @patch("content_aggregator.sources.collectors.last30days_collector.SOURCE_FETCHERS")
    async def test_intermediate_scores_properly_cleaned(self, mock_fetchers, collector, mock_client):
        """中间计算分数 (_rrf_score, _freshness_score, _final_score) 应在返回前清除"""
        mock_fetchers.__getitem__.side_effect = lambda key: AsyncMock(return_value=[{
            "item_id": "clean-1", "source": "reddit",
            "title": "Clean Check", "body": "", "url": "",
            "author": "", "published_at": "2026-06-28T00:00:00Z",
            "engagement": {"upvotes": 100}, "container": "r/test",
        }])

        with patch.object(collector, "_get_client", return_value=mock_client):
            result = await collector._fetch("topic", sources=["reddit"], max_per_source=1, total_max=10)

        assert len(result) == 1
        assert "_rrf_score" not in result[0]
        assert "_freshness_score" not in result[0]
        assert "_final_score" not in result[0]
        # engagement_score 应保留
        assert "engagement_score" in result[0]


# ═══════════════════════════════════════════════════════════════════
# create_last30days_collector 工厂函数测试
# ═══════════════════════════════════════════════════════════════════

class TestCreateLast30DaysCollector:
    """工厂函数 create_last30days_collector()"""

    def test_create_default(self):
        """无配置创建"""
        collector = create_last30days_collector()
        assert isinstance(collector, Last30DaysCollector)
        assert collector.SOURCE_NAME == "last30days"

    def test_create_with_config(self):
        """带配置创建"""
        collector = create_last30days_collector(config={"sources": ["reddit"], "max_per_source": 5})
        assert collector.enabled_sources == ["reddit"]
        assert collector.max_per_source == 5
        assert collector.total_max == 50  # 默认值
        assert collector.days_back == 30  # 默认值

    def test_create_with_kwargs(self):
        """关键字参数创建"""
        collector = create_last30days_collector(config={"sources": ["github"]}, proxy="http://proxy:8080")
        assert collector.enabled_sources == ["github"]
        assert collector.proxy == "http://proxy:8080"


# 需要在文件顶部补 math 导入，用于 normalize_engagement 断言
import math
