"""内置采集器模块"""

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult
from content_aggregator.sources.collectors.rss_collector import RSSCollector
from content_aggregator.sources.collectors.youtube_collector import YouTubeCollector
from content_aggregator.sources.collectors.twitter_collector import TwitterCollector
from content_aggregator.sources.collectors.tiktok_collector import TikTokCollector
from content_aggregator.sources.collectors.douyin_collector import DouyinCollector
from content_aggregator.sources.collectors.xiaohongshu_collector import XiaohongshuCollector
from content_aggregator.sources.collectors.wechat_collector import WeChatCollector
from content_aggregator.sources.collectors.sitemap_collector import SitemapCollector
from content_aggregator.sources.collectors.api_collector import APICollector

__all__ = [
    "BaseCollector",
    "SourceResult",
    "RSSCollector",
    "YouTubeCollector",
    "TwitterCollector",
    "TikTokCollector",
    "DouyinCollector",
    "XiaohongshuCollector",
    "WeChatCollector",
    "SitemapCollector",
    "APICollector",
]