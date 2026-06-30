"""v1 → v2 采集器桥接模块

将 src/content_aggregator/sources/collectors/ 下的 14 个 v1 采集器
桥接到 v2 的 app/services/collect.py 管道中。

设计原则:
1. 懒加载 v1 采集器，缺失依赖时优雅降级（非阻塞）
2. 统一返回 v2 CollectResult 格式
3. 支持单源采集和并行全源采集
4. 代理/限流等由 v1 BaseCollecter 自动处理
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# v1 采集器映射：平台标识 → (采集器类, 显示名称)
# 懒加载，在首次调用时初始化
_COLLECTOR_MAP: dict[str, type] | None = None


def _lazy_load_collectors() -> dict[str, type]:
    """懒加载 v1 采集器映射

    Returns:
        dict[str, type]: 平台标识 → 采集器类 的映射
                         导入失败时返回空字典
    """
    global _COLLECTOR_MAP
    if _COLLECTOR_MAP is not None:
        return _COLLECTOR_MAP

    _COLLECTOR_MAP = {}

    try:
        # 从 v1 __init__.py 导入已注册的采集器
        from content_aggregator.sources.collectors import (  # type: ignore[import-untyped]
            RSSCollector,
            YouTubeCollector,
            TwitterCollector,
            TikTokCollector,
            DouyinCollector,
            XiaohongshuCollector,
            WeChatCollector,
            SitemapCollector,
            APICollector,
            WangYiCollector,
            WeiboHotCollector,
            DouyinHotCollector,
            Last30DaysCollector,
        )

        _COLLECTOR_MAP["rss"] = RSSCollector
        _COLLECTOR_MAP["youtube"] = YouTubeCollector
        _COLLECTOR_MAP["twitter"] = TwitterCollector
        _COLLECTOR_MAP["tiktok"] = TikTokCollector
        _COLLECTOR_MAP["douyin"] = DouyinCollector
        _COLLECTOR_MAP["xiaohongshu"] = XiaohongshuCollector
        _COLLECTOR_MAP["wechat"] = WeChatCollector
        _COLLECTOR_MAP["sitemap"] = SitemapCollector
        _COLLECTOR_MAP["api"] = APICollector
        _COLLECTOR_MAP["wangyi"] = WangYiCollector
        _COLLECTOR_MAP["weibo_hot"] = WeiboHotCollector
        _COLLECTOR_MAP["douyin_hot"] = DouyinHotCollector
        _COLLECTOR_MAP["last30days"] = Last30DaysCollector

        logger.info(
            "v1 采集器桥接已加载: %d 个平台", len(_COLLECTOR_MAP)
        )

    except ImportError as e:
        logger.warning(
            "v1 采集器包未安装（content-aggregator），桥接不可用: %s", e
        )
    except Exception as e:
        logger.warning("加载 v1 采集器时发生异常: %s", e)

    return _COLLECTOR_MAP


def get_available_sources() -> list[str]:
    """返回已加载的可用采集源列表"""
    return list(_lazy_load_collectors().keys())


async def collect_from_source(
    source_name: str,
    proxy: str | None = None,
    config: dict | None = None,
    **kwargs: Any,
) -> list[dict] | None:
    """从指定 v1 采集源采集内容

    用法:
        articles = await collect_from_source("youtube", keyword="AI 编程")
        for art in articles or []:
            print(art["title"])

    Args:
        source_name: 采集器标识 (youtube / twitter / wechat / rss / ...)
        proxy: 可选代理地址（传给 v1 BaseCollecter）
        config: 可选配置字典
        **kwargs: 转发给 v1 采集器的 collect() 的参数

    Returns:
        list[dict] | None: 文章列表（每条含 title/content/url/published_at 等），
                           采集器未找到或导入失败时返回 None
    """
    collectors = _lazy_load_collectors()
    collector_cls = collectors.get(source_name)
    if not collector_cls:
        logger.warning("未知采集源: %s（可用: %s）", source_name, list(collectors.keys()))
        return None

    collector = collector_cls(proxy=proxy, config=config)
    result = await collector.collect(**kwargs)

    if not result.success:
        logger.warning(
            "采集失败 [%s]: %s", source_name, result.error
        )

    articles = result.data if isinstance(result.data, list) else []
    logger.info(
        "采集完成 [%s]: %d 篇 (成功=%d, 跳过=%d, 耗时=%.1fs)",
        source_name,
        len(articles),
        result.collected_count,
        result.skipped_count,
        result.duration,
    )
    return articles


async def collect_all(
    proxy: str | None = None,
    global_config: dict | None = None,
    **kwargs: Any,
) -> dict[str, list[dict] | None]:
    """并行执行所有已加载的 v1 采集器

    Args:
        proxy: 可选代理地址
        global_config: 全局配置（会被每个采集器的 config 合并）
        **kwargs: 转发给所有采集器的全局参数

    Returns:
        dict[str, list[dict] | None]: 平台标识 → 文章列表 的映射
    """
    import asyncio

    collectors = _lazy_load_collectors()
    if not collectors:
        logger.warning("没有可用的 v1 采集器")
        return {}

    async def _collect_one(name: str) -> tuple[str, list[dict] | None]:
        articles = await collect_from_source(
            name,
            proxy=proxy,
            config=global_config,
            **kwargs,
        )
        return name, articles

    tasks = [_collect_one(name) for name in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, list[dict] | None] = {}
    for name, result in zip(collectors.keys(), results):
        if isinstance(result, Exception):
            logger.error("并行采集异常 [%s]: %s", name, result)
            output[name] = None
        else:
            output[name] = result

    return output
