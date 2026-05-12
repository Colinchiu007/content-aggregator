"""
YouTube 采集器

支持：
- 频道最新视频列表（通过 YouTube Data API v3）
- 播放列表视频列表

注意：需要 YouTube Data API Key（免费额度：每天 10000 单位）
无代理/无 API Key 时跳过采集并给出提示，不中断流程。
"""

import logging
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class YouTubeCollector(BaseCollector):
    """YouTube 频道视频采集器"""

    SOURCE_NAME = "youtube"
    RATE_LIMIT = 3.0

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    async def _fetch(self, channel_id: str | None = None, playlist_id: str | None = None,
                     max_results: int = 20, **kwargs) -> list[dict]:
        """
        采集 YouTube 视频

        参数：
            channel_id: YouTube 频道 ID（如 UC...）
            playlist_id: 播放列表 ID（如 LL... 用于获取频道最新视频）
            max_results: 最大条数
        """
        if not self.api_key:
            raise EnvironmentError("YOUTUBE_API_KEY 未配置，请在 config.yaml 中设置 sources.youtube.api_key")

        channel_id = channel_id or self.config.get("channel_id")
        playlist_id = playlist_id or self.config.get("playlist_id")

        if not channel_id and not playlist_id:
            raise ValueError("YouTube 采集器需要 channel_id 或 playlist_id 参数")

        # 构建 API URL
        if playlist_id:
            # 获取频道上传视频的播放列表 ID
            base_url = "https://www.googleapis.com/youtube/v3/playlistItems"
            params = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": min(max_results, 50),
                "key": self.api_key,
            }
        else:
            # 获取频道搜索结果（最新上传）
            base_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "order": "date",
                "maxResults": min(max_results, 50),
                "key": self.api_key,
            }

        client = await self._get_client()
        response = await client.get(base_url, params=params, proxy=self.proxy)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise RuntimeError(f"YouTube API 错误: {data['error'].get('message', 'unknown')}")

        items = data.get("items", [])
        results = []

        for item in items:
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId") or item.get("resourceId", {}).get("videoId", "")

            # 发布时间
            published_str = snippet.get("publishedAt", "")
            published = None
            if published_str:
                try:
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append({
                "title": snippet.get("title", "") or "",
                "content": snippet.get("description", "") or "",
                "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                "author": snippet.get("channelTitle", "") or "",
                "published_at": published,
                "summary": snippet.get("description", "")[:500] or "",
                "tags": [],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "video_id": video_id,
                    "channel_id": snippet.get("channelId", "") or "",
                    "thumbnails": snippet.get("thumbnails", {}),
                }
            })

        logger.info(f"[YouTube] 采集到 {len(results)} 个视频")
        return results