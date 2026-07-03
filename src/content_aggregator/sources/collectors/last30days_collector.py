"""
last30days 多源搜索采集器

继承 BaseCollector，实现 last30days 模式的轻量搜索管线：
- 并行搜索多个海外免费源（Reddit / Hacker News / GitHub / Polymarket）
- engagement_score 归一化管道（log10 跨平台可比化）
- 加权 RRF 融合排序

设计原则：
1. 零配置即可用（4 个免费公开 API）
2. 所有网络错误由基类 BaseCollector.collect() 统一捕获并优雅跳过
3. 跨平台互动数据归一化为 0-1 分，支持公平跨源排序
4. RRF (k=60) 融合各源排名，避免单一源主导搜索结果

MVP 范围（方案 A：轻量集成）：
  [x] Reddit 公开 JSON API 搜索
  [x] Hacker News Algolia API 搜索
  [x] GitHub Issues/Repos 搜索
  [x] Polymarket Gamma API 搜索
  [x] engagement_score 归一化管道
  [x] 基础配置集成（config.yaml 开/关 + 源选择）
  [ ] TrendScope UI 搜索输入框（前端，后续阶段）
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any, Callable

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)

# ── Default Sources ──────────────────────────────────────────────────────────

DEFAULT_SOURCES = ["reddit", "hackernews", "github", "polymarket"]

# ── Engagement Normalization ─────────────────────────────────────────────────

ENGAGEMENT_NORMALIZERS: dict[str, tuple[str, float]] = {
    "reddit":     ("upvotes", 5.0),
    "github":     ("stars", 5.0),
    "hackernews": ("points", 5.0),
    "polymarket": ("volume", 100000.0),
}


def normalize_engagement(source: str, engagement: dict[str, Any]) -> float:
    """Normalize raw engagement metrics to a 0-1 score."""
    normalizer = ENGAGEMENT_NORMALIZERS.get(source)
    if normalizer is None:
        return 0.0
    raw_field, divisor = normalizer
    raw_value = engagement.get(raw_field, 0) or 0
    if source == "polymarket":
        return min(raw_value / divisor, 1.0)
    if isinstance(raw_value, (int, float)) and raw_value > 0:
        return min(math.log10(raw_value + 1) / divisor, 1.0)
    return 0.0


def compute_freshness_score(published_at: datetime | None, days_back: int = 30) -> float:
    """Compute a freshness score (0-1) based on how recent the item is."""
    if published_at is None:
        return 0.5
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_days = (now - published_at).total_seconds() / 86400.0
    if age_days <= 0:
        return 1.0
    if age_days >= days_back:
        return 0.0
    return 1.0 - (age_days / days_back)


def rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score for a single rank position."""
    return 1.0 / (k + rank)


# ── Source Fetchers ──────────────────────────────────────────────────────────


async def _fetch_reddit(client: Any, topic: str, limit: int = 12) -> list[dict]:
    """Search Reddit via public JSON API (no auth required)."""
    url = "https://www.reddit.com/search.json"
    params = {"q": topic, "limit": limit, "sort": "top", "t": "month", "raw_json": 1}
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ContentAggregator/1.0)",
        "Accept": "application/json",
    }
    response = await client.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    items = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
        items.append({
            "item_id": f"reddit-t3_{post.get('id', '')}",
            "source": "reddit",
            "title": post.get("title", "") or "",
            "body": (post.get("selftext", "") or "")[:500],
            "url": f"https://reddit.com{post.get('permalink', '')}",
            "author": post.get("author", "") or "",
            "published_at": created.isoformat(),
            "engagement": {"upvotes": post.get("ups", 0), "comments": post.get("num_comments", 0)},
            "container": post.get("subreddit_name_prefixed", ""),
        })
    return items


async def _fetch_hackernews(client: Any, topic: str, limit: int = 12) -> list[dict]:
    """Search Hacker News via Algolia API (no auth required)."""
    url = "https://hn.algolia.com/api/v1/search"
    params = {
        "query": topic, "hitsPerPage": limit, "tags": "story",
        "numericFilters": "created_at_i>" + str(int(time.time()) - 30 * 86400),
    }
    response = await client.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    items = []
    for hit in data.get("hits", []):
        created = datetime.fromtimestamp(hit.get("created_at_i", 0), tz=timezone.utc)
        items.append({
            "item_id": f"hn-{hit.get('objectID', '')}",
            "source": "hackernews",
            "title": hit.get("title", "") or "",
            "body": (hit.get("story_text", "") or hit.get("comment_text", "") or "")[:500],
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}",
            "author": hit.get("author", "") or "",
            "published_at": created.isoformat(),
            "engagement": {"points": hit.get("points", 0), "comments": hit.get("num_comments", 0)},
            "container": "Hacker News",
        })
    return items


async def _fetch_github(client: Any, topic: str, limit: int = 12) -> list[dict]:
    """Search GitHub Issues and Repositories (no auth required, rate-limited)."""
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "ContentAggregator/1.0"}

    async def _search_issues() -> list[dict]:
        url = "https://api.github.com/search/issues"
        params = {"q": f"{topic} is:public", "sort": "reactions", "order": "desc", "per_page": min(limit, 10)}
        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception:
            return []

    async def _search_repos() -> list[dict]:
        url = "https://api.github.com/search/repositories"
        params = {"q": topic, "sort": "stars", "order": "desc", "per_page": min(limit, 10)}
        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json().get("items", [])
        except Exception:
            return []

    issues_task = asyncio.create_task(_search_issues())
    repos_task = asyncio.create_task(_search_repos())
    issue_items, repo_items = await asyncio.gather(issues_task, repos_task)

    items = []
    for issue in issue_items:
        created = datetime.fromisoformat(issue.get("created_at", "").replace("Z", "+00:00")) if issue.get("created_at") else None
        repo_full = issue.get("repository_url", "").replace("https://api.github.com/repos/", "")
        items.append({
            "item_id": f"github-issue-{issue.get('id', '')}",
            "source": "github", "title": issue.get("title", "") or "",
            "body": (issue.get("body", "") or "")[:500],
            "url": issue.get("html_url", ""),
            "author": issue.get("user", {}).get("login", "") if issue.get("user") else "",
            "published_at": created.isoformat() if created else None,
            "engagement": {"stars": issue.get("score", 0), "comments": issue.get("comments", 0)},
            "container": repo_full or "GitHub",
        })
    for repo in repo_items:
        created = datetime.fromisoformat(repo.get("created_at", "").replace("Z", "+00:00")) if repo.get("created_at") else None
        items.append({
            "item_id": f"github-repo-{repo.get('id', '')}",
            "source": "github",
            "title": f"{repo.get('full_name', '')}: {repo.get('description', '') or ''}",
            "body": (repo.get("description", "") or "")[:500],
            "url": repo.get("html_url", ""),
            "author": repo.get("owner", {}).get("login", "") if repo.get("owner") else "",
            "published_at": created.isoformat() if created else None,
            "engagement": {"stars": repo.get("stargazers_count", 0), "comments": repo.get("open_issues_count", 0)},
            "container": repo.get("full_name", ""),
        })
    return items


async def _fetch_polymarket(client: Any, topic: str, limit: int = 12) -> list[dict]:
    """Search Polymarket events via Gamma API (no auth required)."""
    url = "https://gamma-api.polymarket.com/events"
    params = {"tag": topic, "limit": limit, "closed": "false", "sort": "volume", "order": "desc"}
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        events = response.json()
    except Exception:
        params.pop("tag", None)
        params["title"] = topic
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            events = response.json()
        except Exception:
            return []
    items = []
    for event in events:
        start_date_str = event.get("start_date") or event.get("created_at", "")
        created = None
        if start_date_str:
            try:
                created = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            except Exception:
                pass
        outcomes = event.get("outcomes", [])
        yes_prob = None
        volume = 0
        for outcome in outcomes:
            vol = float(outcome.get("volume", 0) or 0)
            volume += vol
            if outcome.get("outcome", "").lower() == "yes":
                yes_prob = float(outcome.get("price", 0) or 0)
        items.append({
            "item_id": f"polymarket-{event.get('id', '')}",
            "source": "polymarket", "title": event.get("title", "") or "",
            "body": event.get("description", "") or "",
            "url": f"https://polymarket.com/event/{event.get('slug', '')}",
            "author": event.get("creator", {}).get("username", "") if event.get("creator") else "",
            "published_at": created.isoformat() if created else None,
            "engagement": {"volume": volume, "yes_probability": yes_prob},
            "container": event.get("category", "Polymarket"),
        })
    return items


# ── Source Registry ──────────────────────────────────────────────────────────

SOURCE_FETCHERS: dict[str, Callable] = {
    "reddit": _fetch_reddit,
    "hackernews": _fetch_hackernews,
    "github": _fetch_github,
    "polymarket": _fetch_polymarket,
}

# ── Collector ────────────────────────────────────────────────────────────────


class Last30DaysCollector(BaseCollector):
    """Multi-source search collector (last30days pattern).

    Searches across multiple overseas platforms, normalizes engagement
    metrics, and fuses results using RRF ranking.

    Usage:
        collector = Last30DaysCollector(config={"sources": ["reddit", "github"]})
        result = await collector.collect(topic="NVIDIA earnings Q2 2026")
    """

    SOURCE_NAME = "last30days"
    RATE_LIMIT = 1.0

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize collector.

        Config keys:
            sources (list[str]): Enabled sources. Default: 4 free sources.
            max_per_source (int): Max results per source. Default: 12.
            total_max (int): Total max results after fusion. Default: 50.
            days_back (int): Freshness decay window in days. Default: 30.
        """
        super().__init__(*args, **kwargs)
        cfg = self.config or {}
        self.enabled_sources = cfg.get("sources", DEFAULT_SOURCES)
        self.max_per_source = int(cfg.get("max_per_source", 12))
        self.total_max = int(cfg.get("total_max", 50))
        self.days_back = int(cfg.get("days_back", 30))

    async def _fetch(self, topic: str, **kwargs: Any) -> list[dict]:
        """Execute multi-source search for a topic."""
        enabled = list(kwargs.get("sources", self.enabled_sources))
        per_source = int(kwargs.get("max_per_source", self.max_per_source))
        total_max = int(kwargs.get("total_max", self.total_max))
        days_back = int(kwargs.get("days_back", self.days_back))

        valid = [s for s in enabled if s in SOURCE_FETCHERS]
        unknown = set(enabled) - set(SOURCE_FETCHERS)
        if unknown:
            logger.warning(f"[last30days] Unknown sources skipped: {unknown}")
        if not valid:
            logger.warning("[last30days] No valid sources configured")
            return []

        client = await self._get_client()
        tasks: dict[str, asyncio.Task] = {}
        for src in valid:
            fetcher = SOURCE_FETCHERS[src]
            tasks[src] = asyncio.create_task(
                self._safe_fetch(fetcher, client, topic, per_source),
            )

        all_results: dict[str, list[dict]] = {}
        for src, task in tasks.items():
            try:
                all_results[src] = await task
            except Exception as e:
                logger.warning(f"[last30days] {src} fetch failed: {e}")
                all_results[src] = []

        flat: list[dict] = []
        for src, items in all_results.items():
            rank = 1
            for item in items:
                pub_date = self._parse_datetime(item.get("published_at"))
                eng_score = normalize_engagement(src, item.get("engagement", {}))
                fresh_score = compute_freshness_score(pub_date, days_back)
                rr = rrf_score(rank)
                relevance_score = max(0, 1.0 - (rank - 1) * 0.02)
                final = 0.35 * rr + 0.25 * relevance_score + 0.20 * fresh_score + 0.20 * eng_score
                item["_final_score"] = round(final, 4)
                item["engagement_score"] = round(eng_score, 4)
                item["_rrf_score"] = round(rr, 4)
                item["_freshness_score"] = round(fresh_score, 4)
                flat.append(item)
                rank += 1

        seen_ids: set[str] = set()
        deduped: list[dict] = []
        for item in sorted(flat, key=lambda x: x["_final_score"], reverse=True):
            iid = item.get("item_id", "")
            if iid and iid in seen_ids:
                continue
            if iid:
                seen_ids.add(iid)
            deduped.append(item)

        for item in deduped:
            item.pop("_rrf_score", None)
            item.pop("_freshness_score", None)
            item.pop("_final_score", None)

        return deduped[:total_max]

    async def _safe_fetch(self, fetcher: Callable, client: Any, topic: str, limit: int) -> list[dict]:
        try:
            return await fetcher(client, topic, limit)
        except Exception as e:
            logger.warning(f"[last30days] Source fetch error: {e}")
            return []

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except Exception:
                pass
        return None


def create_last30days_collector(config: dict | None = None, **kwargs: Any) -> Last30DaysCollector:
    """Create a configured Last30DaysCollector instance."""
    return Last30DaysCollector(config=config, **kwargs)
