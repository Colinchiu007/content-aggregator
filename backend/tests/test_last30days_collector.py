"""Last30DaysCollector 单元测试 — 全覆盖 32+ 用例"""
from __future__ import annotations

import math
import sys
import types
import importlib.util
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Module bootstrap: load last30days_collector without content_aggregator __init__ ──

src_path = str(Path(__file__).resolve().parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Build minimal package namespace
for pkg in [
    "content_aggregator",
    "content_aggregator.sources",
    "content_aggregator.sources.collectors",
]:
    if pkg not in sys.modules:
        parts = pkg.split(".")
        pkg_dir = Path(src_path) / "/".join(parts)
        mod = types.ModuleType(pkg)
        mod.__path__ = [str(pkg_dir)]
        mod.__package__ = pkg
        sys.modules[pkg] = mod

# Load base_collector dependency
base_path = Path(src_path) / "content_aggregator" / "sources" / "collectors" / "base_collector.py"
base_spec = importlib.util.spec_from_file_location(
    "content_aggregator.sources.collectors.base_collector", str(base_path))
base_mod = importlib.util.module_from_spec(base_spec)
sys.modules["content_aggregator.sources.collectors.base_collector"] = base_mod
base_spec.loader.exec_module(base_mod)

# Load last30days_collector
l30_path = Path(src_path) / "content_aggregator" / "sources" / "collectors" / "last30days_collector.py"
l30_spec = importlib.util.spec_from_file_location(
    "content_aggregator.sources.collectors.last30days_collector", str(l30_path))
l30_mod = importlib.util.module_from_spec(l30_spec)
sys.modules["content_aggregator.sources.collectors.last30days_collector"] = l30_mod
l30_spec.loader.exec_module(l30_mod)

# Now import
from content_aggregator.sources.collectors.last30days_collector import (
    Last30DaysCollector,
    normalize_engagement,
    compute_freshness_score,
    rrf_score,
    SOURCE_FETCHERS,
    DEFAULT_SOURCES,
    ENGAGEMENT_NORMALIZERS,
    create_last30days_collector,
)

# ═════════════════════════════════════════════════════════════════════════════
# normalize_engagement
# ═════════════════════════════════════════════════════════════════════════════


class TestNormalizeEngagement:
    def test_reddit_upvotes_high(self):
        score = normalize_engagement("reddit", {"upvotes": 1000})
        assert 0 < score <= 1.0
        assert score == pytest.approx(min(math.log10(1001) / 5.0, 1.0))

    def test_reddit_upvotes_zero(self):
        assert normalize_engagement("reddit", {"upvotes": 0}) == 0.0

    def test_github_stars_high(self):
        score = normalize_engagement("github", {"stars": 5000})
        assert score == pytest.approx(min(math.log10(5001) / 5.0, 1.0))

    def test_github_stars_missing(self):
        assert normalize_engagement("github", {}) == 0.0

    def test_hackernews_points(self):
        score = normalize_engagement("hackernews", {"points": 200})
        assert score == pytest.approx(min(math.log10(201) / 5.0, 1.0))

    def test_polymarket_volume_linear(self):
        assert normalize_engagement("polymarket", {"volume": 50000}) == pytest.approx(0.5)

    def test_polymarket_volume_capped(self):
        assert normalize_engagement("polymarket", {"volume": 200000}) == 1.0

    def test_polymarket_volume_zero(self):
        assert normalize_engagement("polymarket", {"volume": 0}) == 0.0

    def test_log10_capped(self):
        assert normalize_engagement("reddit", {"upvotes": 10_000_000}) == 1.0

    def test_unknown_source_zero(self):
        assert normalize_engagement("unknown_source", {"upvotes": 100}) == 0.0


# ═════════════════════════════════════════════════════════════════════════════
# compute_freshness_score
# ═════════════════════════════════════════════════════════════════════════════


class TestComputeFreshnessScore:
    def test_now_is_1(self):
        assert compute_freshness_score(datetime.now(timezone.utc)) == pytest.approx(1.0, abs=0.01)

    def test_15_days_ago(self):
        dt = datetime.now(timezone.utc) - timedelta(days=15)
        assert 0.4 < compute_freshness_score(dt) < 0.6

    def test_30_days_ago(self):
        assert compute_freshness_score(
            datetime.now(timezone.utc) - timedelta(days=30)
        ) == 0.0

    def test_over_30_days(self):
        assert compute_freshness_score(
            datetime.now(timezone.utc) - timedelta(days=60)
        ) == 0.0

    def test_none(self):
        assert compute_freshness_score(None) == 0.5

    def test_naive_datetime(self):
        assert 0.3 < compute_freshness_score(
            datetime.now() - timedelta(days=10)
        ) < 0.7

    def test_future_date(self):
        assert compute_freshness_score(
            datetime.now(timezone.utc) + timedelta(days=1)
        ) == 1.0

    def test_custom_days_back(self):
        assert 0.5 < compute_freshness_score(
            datetime.now(timezone.utc) - timedelta(days=3), days_back=7
        ) < 0.65


# ═════════════════════════════════════════════════════════════════════════════
# rrf_score
# ═════════════════════════════════════════════════════════════════════════════


class TestRRFScore:
    def test_rank_1(self):
        assert rrf_score(1) == pytest.approx(1.0 / 61.0)

    def test_rank_10(self):
        assert rrf_score(10) == pytest.approx(1.0 / 70.0)

    def test_rank_60(self):
        assert rrf_score(60) == pytest.approx(1.0 / 120.0)

    def test_custom_k(self):
        assert rrf_score(1, k=100) == pytest.approx(1.0 / 101.0)


# ═════════════════════════════════════════════════════════════════════════════
# Last30DaysCollector 集成测试
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


def _make_mock_response(json_data: Any, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=json_data)
    resp.raise_for_status = MagicMock()
    return resp


class TestLast30DaysCollectorUnit:
    REDDIT_RESPONSE = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc123",
                        "title": "Test Reddit Post",
                        "selftext": "Body",
                        "permalink": "/r/test/comments/abc123/p/",
                        "author": "u",
                        "created_utc": 1717000000,
                        "ups": 500,
                        "num_comments": 50,
                        "subreddit_name_prefixed": "r/test",
                    }
                }
            ]
        }
    }

    HN_RESPONSE = {
        "hits": [
            {
                "objectID": "12345",
                "title": "Test HN Story",
                "story_text": "Story",
                "url": "https://example.com/s",
                "author": "hnu",
                "created_at_i": 1717000000,
                "points": 150,
                "num_comments": 30,
            }
        ]
    }

    async def _setup(self, mock_client, config=None):
        collector = Last30DaysCollector(config=config or {})
        collector._get_client = AsyncMock(return_value=mock_client)
        return collector

    @pytest.mark.asyncio
    async def test_fetch_all_sources_success(self, mock_client):
        mock_client.get = AsyncMock(side_effect=[
            _make_mock_response(self.REDDIT_RESPONSE),
            _make_mock_response(self.HN_RESPONSE),
            _make_mock_response({"items": [{"id": 1, "full_name": "r1", "stargazers_count": 100}]}),
            _make_mock_response([]),
        ])
        c = await self._setup(mock_client)
        result = await c._fetch("AI")
        assert len(result) > 0
        assert mock_client.get.call_count >= 4

    @pytest.mark.asyncio
    async def test_unknown_source_skipped(self, mock_client):
        mock_client.get = AsyncMock(return_value=_make_mock_response(self.REDDIT_RESPONSE))
        c = await self._setup(mock_client, {"sources": ["reddit", "unknown"]})
        result = await c._fetch("t")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_no_valid_sources(self, mock_client):
        c = await self._setup(mock_client, {"sources": ["nonexistent"]})
        assert await c._fetch("t") == []

    @pytest.mark.asyncio
    async def test_one_source_fails_others_succeed(self, mock_client):
        async def _get(url, **kwargs):
            if "reddit" in str(url):
                raise Exception("fail")
            return _make_mock_response(self.HN_RESPONSE)
        mock_client.get = _get
        c = await self._setup(mock_client, {"sources": ["reddit", "hackernews"]})
        result = await c._fetch("t")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_empty_all_sources(self, mock_client):
        mock_client.get = AsyncMock(return_value=_make_mock_response({"data": {"children": []}}))
        c = await self._setup(mock_client, {"sources": ["reddit"]})
        assert await c._fetch("t") == []

    @pytest.mark.asyncio
    async def test_deduplication(self, mock_client):
        mock_client.get = AsyncMock(return_value=_make_mock_response(self.REDDIT_RESPONSE))
        c = await self._setup(mock_client, {"sources": ["reddit", "reddit"]})
        result = await c._fetch("t")
        ids = [i.get("item_id") for i in result]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_custom_max_per_source(self, mock_client):
        many = {"data": {"children": [
            {"data": {"id": str(i), "title": str(i), "permalink": f"/r/t/{i}/p/",
                      "author": "u", "created_utc": 1717000000 + i,
                      "ups": 10, "num_comments": 1, "subreddit_name_prefixed": "r/t"}}
            for i in range(3)
        ]}}
        mock_client.get = AsyncMock(return_value=_make_mock_response(many))
        c = await self._setup(mock_client, {"sources": ["reddit"], "max_per_source": 3})
        result = await c._fetch("t")
        assert len(result) <= 3
        # Verify API called with expected limit parameter
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs.get("params", {}).get("limit") == 3

    @pytest.mark.asyncio
    async def test_total_max_limit(self, mock_client):
        many = {"data": {"children": [
            {"data": {"id": str(i), "title": str(i), "permalink": f"/r/t/{i}/p/",
                      "author": "u", "created_utc": 1717000000 + i,
                      "ups": 10, "num_comments": 1, "subreddit_name_prefixed": "r/t"}}
            for i in range(10)
        ]}}
        mock_client.get = AsyncMock(return_value=_make_mock_response(many))
        c = await self._setup(mock_client, {"sources": ["reddit"], "total_max": 3})
        assert len(await c._fetch("t")) <= 3

    @pytest.mark.asyncio
    async def test_collect_method_success(self, mock_client):
        mock_client.get = AsyncMock(return_value=_make_mock_response(self.REDDIT_RESPONSE))
        c = await self._setup(mock_client)
        sr = await c.collect(topic="AI")
        assert sr.success is True
        assert sr.source_name == "last30days"
        assert len(sr.data) > 0

    @pytest.mark.asyncio
    async def test_collect_method_all_empty(self, mock_client):
        mock_client.get = AsyncMock(return_value=_make_mock_response({"data": {"children": []}}))
        c = await self._setup(mock_client, {"sources": ["reddit"]})
        sr = await c.collect(topic="nothing")
        assert sr.success is True
        assert sr.data == []

    @pytest.mark.asyncio
    async def test_parse_datetime_iso(self):
        c = Last30DaysCollector()
        dt = c._parse_datetime("2026-06-01T12:00:00+00:00")
        assert dt is not None and dt.year == 2026 and dt.month == 6

    def test_parse_datetime_none(self):
        assert Last30DaysCollector()._parse_datetime(None) is None

    def test_parse_datetime_datetime_obj(self):
        now = datetime.now(timezone.utc)
        assert Last30DaysCollector()._parse_datetime(now) is now

    def test_parse_datetime_invalid(self):
        assert Last30DaysCollector()._parse_datetime("not-a-date") is None

    def test_create_last30days_collector(self):
        c = create_last30days_collector({"sources": ["reddit"]})
        assert isinstance(c, Last30DaysCollector)
        assert c.enabled_sources == ["reddit"]

    def test_default_config(self):
        c = Last30DaysCollector()
        assert c.enabled_sources == DEFAULT_SOURCES
        assert c.max_per_source == 12 and c.total_max == 50 and c.days_back == 30

    def test_custom_config(self):
        c = Last30DaysCollector(config={
            "sources": ["github"], "max_per_source": 5,
            "total_max": 20, "days_back": 7,
        })
        assert c.enabled_sources == ["github"]
        assert c.max_per_source == 5 and c.total_max == 20 and c.days_back == 7

    def test_source_fetchers_registered(self):
        assert set(SOURCE_FETCHERS.keys()) == {"reddit", "hackernews", "github", "polymarket"}

    def test_engagement_normalizers_registered(self):
        assert set(ENGAGEMENT_NORMALIZERS.keys()) == {"reddit", "github", "hackernews", "polymarket"}


# ═════════════════════════════════════════════════════════════════════════════
# 评分公式验证
# ═════════════════════════════════════════════════════════════════════════════


class TestScoringFormula:
    def test_normalization_range(self):
        cases = [
            ("reddit", {"upvotes": 0}), ("reddit", {"upvotes": 1_000_000}),
            ("github", {"stars": 0}), ("github", {"stars": 1_000_000}),
            ("hackernews", {"points": 0}), ("hackernews", {"points": 100_000}),
            ("polymarket", {"volume": 0}), ("polymarket", {"volume": 999_999_999}),
        ]
        for src, eng in cases:
            assert 0 <= normalize_engagement(src, eng) <= 1.0, f"{src} {eng}"

    def test_freshness_range(self):
        now = datetime.now(timezone.utc)
        assert compute_freshness_score(now) == pytest.approx(1.0, abs=0.01)
        assert compute_freshness_score(now - timedelta(days=15)) == pytest.approx(0.5, abs=0.01)
        assert compute_freshness_score(now - timedelta(days=30)) == 0.0
        assert compute_freshness_score(None) == 0.5
