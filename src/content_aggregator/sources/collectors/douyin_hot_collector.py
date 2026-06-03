"""
抖音热点（热榜）采集器

抖音热榜接口：https://www.douyin.com/aweme/v1/web/hot/search/list/
- 热榜数据公开，可免登录访问
- 返回当前热门话题/视频列表

与 douyin_collector.py 的区别：
- douyin_collector: 采集指定用户的视频列表（需要 Cookie 或 client_key）
- douyin_hot_collector: 采集抖音热榜（公开数据，无需登录）
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult
from content_aggregator.anti_block import AntiBlockManager, create_default_manager

logger = logging.getLogger(__name__)


class DouyinHotCollector(BaseCollector):
    """抖音热点（热榜）采集器"""

    SOURCE_NAME = "douyin_hot"
    RATE_LIMIT = 5.0  # 抖音反爬较严

    # 抖音热榜 API
    HOT_SEARCH_URL = "https://www.douyin.com/aweme/v1/web/hot/search/list/"

    def __init__(
        self,
        proxy: str | None = None,
        timeout: int = 30,
        config: dict | None = None,
        enable_anti_block: bool = False,
        **kwargs,
    ):
        super().__init__(proxy=proxy, timeout=timeout, config=config, **kwargs)
        self.limit = self.config.get("limit", 20)  # 默认取前20条热榜
        self.enable_anti_block = enable_anti_block
        self.anti_block_manager: AntiBlockManager | None = None

        if enable_anti_block:
            self.anti_block_manager = create_default_manager(enable_proxy=proxy is not None)
            logger.info("[抖音热点] 防封采集机制已启用")

    async def _fetch(self, **kwargs) -> list[dict]:
        """采集抖音热榜"""
        import time
        start = time.time()

        # 调用热榜 API
        hot_list = await self._fetch_hot_list()
        if not hot_list:
            return []

        logger.info(f"[抖音热点] 获取到 {len(hot_list)} 条热榜")

        # 截取前 N 条
        if self.limit > 0:
            hot_list = hot_list[: self.limit]

        logger.info(f"[抖音热点] 采集完成，共 {len(hot_list)} 条")
        return hot_list

    async def _fetch_hot_list(self) -> list[dict]:
        """获取抖音热榜"""
        if self.enable_anti_block and self.anti_block_manager:
            return await self._fetch_with_anti_block()
        else:
            return await self._fetch_normal()

    async def _fetch_normal(self) -> list[dict]:
        """普通模式获取热榜"""
        client = await self._get_client()
        await self._rate_limit_wait()

        # 抖音热榜 API 需要特定的请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.douyin.com/discover",
            "Cookie": self.config.get("cookie", ""),
        }

        # 热榜 API 参数
        params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "version_code": "190500",
            "version_name": "19.5.0",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "120.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "120.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "8",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "100",
        }

        response = await client.get(self.HOT_SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data.get("data"):
            logger.warning("[抖音热点] 返回数据为空")
            return []

        hot_list = data["data"].get("word_list", [])
        if not hot_list:
            logger.warning("[抖音热点] word_list 为空")
            return []

        results = []
        for item in hot_list:
            rank = item.get("rank", 0)
            word = item.get("word", "")
            hot_value = item.get("hot_value", 0)
            video_count = item.get("video_count", 0)
            event_time = item.get("event_time", 0)

            # 热度标识
            heat_label = ""
            if hot_value > 1000000:
                heat_label = "爆"
            elif hot_value > 500000:
                heat_label = "热"
            elif item.get("is_new", 0) == 1:
                heat_label = "新"

            # 构建视频链接（如果有 top_video）
            video_url = ""
            top_video = item.get("top_video", {})
            if top_video:
                aweme_id = top_video.get("aweme_id", "")
                if aweme_id:
                    video_url = f"https://www.douyin.com/video/{aweme_id}"

            results.append({
                "title": word,
                "url": video_url or f"https://www.douyin.com/search/{word}",
                "source": self.SOURCE_NAME,
                "rank": rank,
                "hot_value": hot_value,
                "video_count": video_count,
                "heat_label": heat_label,
                "word": word,
                "published_at": datetime.fromtimestamp(event_time) if event_time else datetime.now(),
                "summary": f"抖音热榜第{rank}名，热度{hot_value:,}，相关视频{video_count}个{heat_label and f'（{heat_label}）' or ''}",
                "metadata": {
                    "rank": rank,
                    "hot_value": hot_value,
                    "video_count": video_count,
                    "heat_label": heat_label,
                    "event_time": event_time,
                },
            })

        return results

    async def _fetch_with_anti_block(self) -> list[dict]:
        """防封模式获取热榜"""
        import asyncio
        import json
        loop = asyncio.get_event_loop()

        params = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "version_code": "190500",
            "version_name": "19.5.0",
            "cookie_enabled": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "120.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "120.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "8",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "100",
        }

        def _do_fetch():
            return self.anti_block_manager.request(
                "GET", self.HOT_SEARCH_URL, params=params, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.douyin.com/discover",
                }
            )

        response = await loop.run_in_executor(None, _do_fetch)
        data = json.loads(response.text)

        if not data.get("data"):
            return []

        hot_list = data["data"].get("word_list", [])
        results = []
        for item in hot_list:
            rank = item.get("rank", 0)
            word = item.get("word", "")
            hot_value = item.get("hot_value", 0)
            video_count = item.get("video_count", 0)
            event_time = item.get("event_time", 0)

            heat_label = ""
            if hot_value > 1000000:
                heat_label = "爆"
            elif hot_value > 500000:
                heat_label = "热"
            elif item.get("is_new", 0) == 1:
                heat_label = "新"

            video_url = ""
            top_video = item.get("top_video", {})
            if top_video:
                aweme_id = top_video.get("aweme_id", "")
                if aweme_id:
                    video_url = f"https://www.douyin.com/video/{aweme_id}"

            results.append({
                "title": word,
                "url": video_url or f"https://www.douyin.com/search/{word}",
                "source": self.SOURCE_NAME,
                "rank": rank,
                "hot_value": hot_value,
                "video_count": video_count,
                "heat_label": heat_label,
                "word": word,
                "published_at": datetime.fromtimestamp(event_time) if event_time else datetime.now(),
                "summary": f"抖音热榜第{rank}名，热度{hot_value:,}，相关视频{video_count}个{heat_label and f'（{heat_label}）' or ''}",
                "metadata": {
                    "rank": rank,
                    "hot_value": hot_value,
                    "video_count": video_count,
                    "heat_label": heat_label,
                },
            })

        return results

    async def fetch_hot_video_detail(self, url: str) -> dict | None:
        """
        获取热榜中关联视频的详情

        如果热榜项包含 top_video，可以进一步获取该视频完整信息
        """
        import re

        # 从 URL 提取 aweme_id
        match = re.search(r'douyin\.com/video/(\d+)', url)
        if not match:
            return None

        aweme_id = match.group(1)
        detail_url = "https://www.douyin.com/aweme/v1/web/aweme/detail/"

        client = await self._get_client()
        await self._rate_limit_wait()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": self.config.get("cookie", ""),
        }

        params = {
            "aweme_id": aweme_id,
            "device_platform": "webapp",
            "aid": "6383",
        }

        try:
            response = await client.get(detail_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.warning(f"[抖音热点] 获取视频详情失败 {aweme_id}: {e}")
            return None

        aweme_detail = data.get("aweme_detail", {})
        if not aweme_detail:
            return None

        video_info = aweme_detail.get("video", {})
        stats = aweme_detail.get("statistics", {})
        author = aweme_detail.get("author", {})
        desc = aweme_detail.get("desc", "")

        published_str = aweme_detail.get("create_time", "")
        published_at = None
        if published_str:
            try:
                published_at = datetime.fromtimestamp(int(published_str))
            except Exception:
                pass

        # 获取视频播放地址
        play_url = ""
        play_addr = video_info.get("play_addr", {}).get("url_list", [])
        if play_addr:
            play_url = play_addr[0]

        return {
            "title": desc[:100] if desc else "",
            "content": desc,
            "url": f"https://www.douyin.com/video/{aweme_id}",
            "source": self.SOURCE_NAME,
            "author": author.get("nickname", "") or author.get("unique_id", ""),
            "published_at": published_at,
            "summary": desc[:300] if desc else "",
            "metadata": {
                "aweme_id": aweme_id,
                "likes": stats.get("digg_count", 0),
                "views": stats.get("play_count", 0),
                "comments": stats.get("comment_count", 0),
                "video_url": play_url,
            },
        }
