"""数据源模块 — Phase 2 已迁移至 shared 库"""

import logging
logger = logging.getLogger(__name__)

from content_aggregator.sources.base import BaseSource, SourceConfig, TestResult
from content_aggregator.sources.rss import RSSCollector
from content_aggregator_shared.shared.collectors import (
    RSSCollector as CollectorsRSS,
    YouTubeCollector,
    TwitterCollector,
    TikTokCollector,
    DouyinCollector,
    DouyinHotCollector,
    WangYiCollector,
    WeiboHotCollector,
    XiaohongshuCollector,
    WeChatCollector,
    SitemapCollector,
    APICollector,
    SourceResult,
    BaseCollector,
)
from content_aggregator_shared.shared.collectors.factory import get_collector

__all__ = [
    "BaseSource",
    "SourceConfig",
    "TestResult",
    "RSSCollector",
    "CollectorsRSS",
    "YouTubeCollector",
    "TwitterCollector",
    "TikTokCollector",
    "DouyinCollector",
    "DouyinHotCollector",
    "WangYiCollector",
    "WeiboHotCollector",
    "XiaohongshuCollector",
    "WeChatCollector",
    "SitemapCollector",
    "APICollector",
    "SourceResult",
    "BaseCollector",
    "get_collector",
]
