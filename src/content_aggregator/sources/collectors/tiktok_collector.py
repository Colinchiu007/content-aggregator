"""
抖音/TikTok 采集器

支持：
- 创作者主页视频列表（通过官方 API 或第三方工具）
- 关键词搜索视频

注意：
- 抖音/TikTok 均需要特殊接口或 Cookie，配置复杂
- 国内抖音需抖音开放平台应用，无配置时跳过并提示
- TikTok 同理，无配置时跳过
"""

import logging

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class TikTokCollector(BaseCollector):
    """TikTok 视频采集器"""

    SOURCE_NAME = "tiktok"
    RATE_LIMIT = 5.0

    def __init__(self, session_id: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id

    async def _fetch(self, sec_uid: str | None = None, username: str | None = None,
                     max_results: int = 20, **kwargs) -> list[dict]:
        """
        采集 TikTok 视频

        参数：
            sec_uid: TikTok 用户的 sec_uid（通过 TikTok API 获取）
            username: 用户名
            max_results: 最大条数
        """
        if not self.session_id:
            raise EnvironmentError(
                "TIKTOK_SESSION_ID 未配置，请在 config.yaml 中设置 sources.tiktok.session_id "
                "（需登录 TikTok Web 后获取 Cookie 中的 sessionid）"
            )

        sec_uid = sec_uid or self.config.get("sec_uid")
        username = username or self.config.get("username")

        if not sec_uid and not username:
            raise ValueError("TikTok 采集器需要 sec_uid 或 username 参数")

        client = await self._get_client()

        # TikTok 公开接口（可能需要 Cookie）
        url = "https://www.tiktok.com/api/post/item_list/"
        params = {
            "aid": "1988",
            "count": min(max_results, 20),
            "sec_user_id": sec_uid or "",
            "max_cursor": 0,
            "use_native_aggregate": 1,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        }
        if self.session_id:
            headers["Cookie"] = f"sessionid={self.session_id}"

        response = await client.get(url, params=params, headers=headers, proxy=self.proxy)
        response.raise_for_status()
        data = response.json()

        items = data.get("itemList", []) or data.get("item_list", [])
        results = []

        for item in items:
            results.append({
                "title": item.get("desc", "") or "",
                "content": item.get("desc", "") or "",
                "url": f"https://www.tiktok.com/@{item.get('author', {}).get('uniqueId', '')}/video/{item.get('id', '')}",
                "author": item.get("author", {}).get("nickname", "") or "",
                "published_at": None,
                "summary": item.get("desc", "")[:300] or "",
                "tags": [t.get("title", "") for t in item.get("challenges", [])],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "video_id": item.get("id", ""),
                    "likes": item.get("stats", {}).get("digg_count", 0),
                    "views": item.get("stats", {}).get("play_count", 0),
                }
            })

        logger.info(f"[TikTok] 采集到 {len(results)} 个视频")
        return results