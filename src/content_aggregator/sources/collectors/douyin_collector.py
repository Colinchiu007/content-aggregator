"""
抖音国内版采集器

支持：
- 创作者主页视频列表（通过抖音开放平台 API 或 Cookie）
- 关键词搜索

注意：
- 需要抖音开放平台应用 Key，或登录 Cookie
- 无配置时跳过并给出友好提示
- 支持代理（国内访问抖音无需代理）
"""

import logging
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class DouyinCollector(BaseCollector):
    """抖音国内版采集器"""

    SOURCE_NAME = "douyin"
    RATE_LIMIT = 3.0

    def __init__(self, cookie: str | None = None, client_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cookie = cookie
        self.client_key = client_key

    async def _fetch(self, sec_uid: str | None = None, username: str | None = None,
                     max_results: int = 20, **kwargs) -> list[dict]:
        """
        采集抖音视频

        参数：
            sec_uid: 抖音用户 sec_uid
            username: 抖音号/用户名
            max_results: 最大条数
        """
        if not self.cookie and not self.client_key:
            raise EnvironmentError(
                "DOUYIN_COOKIE 或 DOUYIN_CLIENT_KEY 未配置，请在 config.yaml 中设置 sources.douyin.cookie "
                "（登录抖音网页后获取）或 sources.douyin.client_key（抖音开放平台应用）"
            )

        sec_uid = sec_uid or self.config.get("sec_uid")
        username = username or self.config.get("username")

        client = await self._get_client()
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        if self.cookie:
            headers["Cookie"] = self.cookie

        url = "https://www.douyin.com/aweme/v1/web/aweme/post/"
        params = {
            "sec_user_id": sec_uid or "",
            "count": min(max_results, 20),
            "max_cursor": 0,
            "cookie_enabled": 1,
            "platform": "PC",
            "downlink": 10,
        }

        try:
            response = await client.get(url, params=params, headers=headers, proxy=self.proxy)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            # 抖音 API 较严格，尝试备用接口
            logger.warning(f"[Douyin] 主接口失败，尝试备用: {e}")
            # 备用：使用搜索接口
            url2 = "https://www.douyin.com/aweme/v1/web/general/search/single/"
            params2 = {
                "keyword": username or sec_uid or "",
                "search_channel": "aweme_user_web",
                "enable_history": 1,
                "pc_client_type": 1,
            }
            response = await client.get(url2, params=params2, headers=headers, proxy=self.proxy)
            response.raise_for_status()
            data = response.json()

        aweme_list = data.get("aweme_list", []) or data.get("awemeData", {}).get("aweme_list", [])
        results = []

        for item in aweme_list:
            video_info = item.get("video", {})
            stats = item.get("statistics", {})
            author = item.get("author", {})

            published_str = item.get("create_time", "")
            published = None
            if published_str:
                try:
                    published = datetime.fromtimestamp(int(published_str))
                except Exception:
                    pass

            results.append({
                "title": item.get("desc", "") or "",
                "content": item.get("desc", "") or "",
                "url": f"https://www.douyin.com/video/{item.get('aweme_id', '')}",
                "author": author.get("nickname", "") or author.get("unique_id", "") or "",
                "published_at": published,
                "summary": item.get("desc", "")[:300] or "",
                "tags": [t.get("hashtag_name", "") for t in item.get("text_extra", [])],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "aweme_id": item.get("aweme_id", ""),
                    "likes": stats.get("digg_count", 0),
                    "views": stats.get("play_count", 0),
                    "comments": stats.get("comment_count", 0),
                }
            })

        logger.info(f"[Douyin] 采集到 {len(results)} 个视频")
        return results