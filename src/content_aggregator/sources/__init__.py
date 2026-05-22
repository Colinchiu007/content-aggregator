"""数据源模块"""

import logging

from content_aggregator.sources.base import BaseSource, SourceConfig, TestResult
from content_aggregator.sources.rss import RSSCollector
from content_aggregator.sources.collectors import (
    RSSCollector as CollectorsRSS,
    YouTubeCollector,
    TwitterCollector,
    TikTokCollector,
    DouyinCollector,
    XiaohongshuCollector,
    WeChatCollector,
    SitemapCollector,
    APICollector,
    SourceResult,
    BaseCollector,
)

__all__ = [
    "BaseSource",
    "SourceConfig",
    "TestResult",
    "RSSCollector",
    # 新采集器
    "CollectorsRSS",
    "YouTubeCollector",
    "TwitterCollector",
    "TikTokCollector",
    "DouyinCollector",
    "XiaohongshuCollector",
    "WeChatCollector",
    "SitemapCollector",
    "APICollector",
    "SourceResult",
    "BaseCollector",
]


def get_collector(source_type: str, config: dict | None = None, **kwargs):
    """
    根据 source_type 获取对应采集器

    source_type 支持：rss, youtube, twitter, tiktok, douyin, xiaohongshu, wechat, sitemap, api
    """
    # 读全局 proxy 配置
    import os
    proxy = kwargs.pop("proxy", os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY"))
    timeout = kwargs.pop("timeout", 30)

    mapping = {
        "rss": (CollectorsRSS, ["url"]),
        "youtube": (YouTubeCollector, ["channel_id", "playlist_id"]),
        "twitter": (TwitterCollector, ["username", "query"]),
        "tiktok": (TikTokCollector, ["sec_uid", "username"]),
        "douyin": (DouyinCollector, ["sec_uid", "username"]),
        "xiaohongshu": (XiaohongshuCollector, ["user_id", "keyword"]),
        "wechat": (WeChatCollector, ["biz", "name"]),
        "sitemap": (SitemapCollector, ["base_url"]),
        "api": (APICollector, ["api_url"]),
    }

    if source_type not in mapping:
        raise ValueError(f"未知的数据源类型: {source_type}，支持: {list(mapping.keys())}")

    collector_cls, required_fields = mapping[source_type]

    # 从 config 中提取配置
    source_cfg = config or {}
    init_kwargs = {"proxy": proxy, "timeout": timeout}

    # API Key / Cookie 等特殊字段
    key_fields = {
        "youtube": "api_key",
        "twitter": "bearer_token",
        "tiktok": "session_id",
        "douyin": ("cookie", "client_key"),
        "xiaohongshu": ("cookie", "xhs_token"),
        "wechat": "api_key",
    }

    if source_type in key_fields:
        keys = key_fields[source_type]
        if isinstance(keys, str):
            keys = [keys]
        for k in keys:
            if k in source_cfg:
                init_kwargs[k] = source_cfg[k]

    # YouTube 字幕提取：传入 LLM 配置（用于无字幕时的 AI 识别）
    if source_type == "youtube":
        init_kwargs["fetch_transcript"] = source_cfg.get("fetch_transcript", True)
        # 从 config.yaml 的顶层 llm 节读取
        if "llm" in source_cfg:
            init_kwargs["llm_config"] = source_cfg["llm"]

    # 传入 config 字典（采集器从中读取参数）
    init_kwargs["config"] = source_cfg

    collector = collector_cls(**init_kwargs)

    # 记录 source_type
    collector.source_type = source_type

    return collector