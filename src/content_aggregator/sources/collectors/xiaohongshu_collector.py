"""
小红书采集器

支持：
- 用户笔记列表（通过小红书 API 或 Cookie）
- 关键词搜索

注意：
- 小红书 API 需要 Cookie 或 Access Token
- 无配置时跳过并给出友好提示
"""

import logging
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class XiaohongshuCollector(BaseCollector):
    """小红书笔记采集器"""

    SOURCE_NAME = "xiaohongshu"
    RATE_LIMIT = 3.0

    def __init__(self, cookie: str | None = None, xhs_token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.cookie = cookie
        self.xhs_token = xhs_token

    async def _fetch(self, user_id: str | None = None, keyword: str | None = None,
                     max_results: int = 20, **kwargs) -> list[dict]:
        """
        采集小红书笔记

        参数：
            user_id: 小红书用户 ID（主页链接中的 user_id）
            keyword: 搜索关键词
            max_results: 最大条数
        """
        if not self.cookie and not self.xhs_token:
            raise EnvironmentError(
                "XHS_COOKIE 未配置，请在 config.yaml 中设置 sources.xiaohongshu.cookie "
                "（登录小红书网页后获取 Cookie）"
            )

        user_id = user_id or self.config.get("user_id")
        keyword = keyword or self.config.get("keyword")

        client = await self._get_client()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": self.cookie or "",
            "X-s": self.xhs_token or "",
            "Referer": "https://www.xiaohongshu.com/",
        }

        if user_id:
            # 用户笔记列表
            url = "https://edith.xiaohongshu.com/api/sns/web/v1/user_posted"
            params = {
                "user_id": user_id,
                "cursor": "",
                "num": min(max_results, 20),
                "image_scenes": "MAIN",
            }
        elif keyword:
            # 搜索
            url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
            params = {
                "keyword": keyword,
                "page": 1,
                "page_size": min(max_results, 20),
                "search_channel": "home_feed_direct",
            }
        else:
            raise ValueError("小红书采集器需要 user_id 或 keyword 参数")

        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"小红书 API 错误: {data.get('msg', data)}")

        items = data.get("data", {}).get("notes", []) or data.get("items", [])
        results = []

        for item in items:
            note_card = item.get("note_card", item)
            author = note_card.get("user", {})

            published_str = note_card.get("time", "") or note_card.get("created_at", "")
            published = None
            if published_str:
                try:
                    published = datetime.fromtimestamp(int(published_str))
                except Exception:
                    try:
                        from datetime import timezone
                        published = datetime.fromisoformat(published_str).replace(tzinfo=None)
                    except Exception:
                        pass

            results.append({
                "title": note_card.get("display_title", "") or note_card.get("title", "") or "",
                "content": note_card.get("desc", "") or "",
                "url": f"https://www.xiaohongshu.com/explore/{note_card.get('id', '')}",
                "author": author.get("nickname", "") or "",
                "published_at": published,
                "summary": note_card.get("desc", "")[:300] or "",
                "tags": note_card.get("tag_list", []) or [],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "note_id": note_card.get("id", ""),
                    "type": note_card.get("type", ""),
                    "likes": note_card.get("interact_info", {}).get("liked_count", 0),
                }
            })

        logger.info(f"[小红书] 采集到 {len(results)} 篇笔记")
        return results