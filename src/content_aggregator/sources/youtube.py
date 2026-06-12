"""
YouTube 数据源

使用 YouTube Data API v3 采集频道/播放列表的视频内容。
获取视频标题、描述、发布时间，可选抓取字幕作为正文内容。

配置示例：
  sources:
    youtube:
      name: YouTube
      type: youtube
      enabled: true
      config:
        api_key: "YOUR_YOUTUBE_API_KEY"
        channels:
          - channel_id: "UC_x5XG1OV2P6uZZ5FSM9Ttw"
            name: "Google Developers"
            max_videos: 10
          - channel_id: "UCSHZKyawb77ixDdsGog4iWA"
            name: "Fireship"
            max_videos: 5
        fetch_transcripts: false   # 是否抓取字幕（需额外依赖）
"""

import asyncio
import httpx
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from loguru import logger

from content_aggregator.sources.base import BaseSource, SourceConfig, TestResult
from content_aggregator.models import Content
from content_aggregator.clients.llm_utils import (
    looks_like_youtube_bot_challenge,
    looks_like_format_selection_error,
    summarize_yt_error,
)


class YouTubeSource(BaseSource):
    """YouTube 数据源"""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, config: SourceConfig, proxy: str | None = None):
        super().__init__(config)
        self.api_key = config.config.get("api_key", "")
        self.channels = config.config.get("channels", [])
        self.search_queries = config.config.get("search_queries", [])  # 新增：搜索关键词列表
        self.search_limit = config.config.get("search_limit", 5)  # 新增：每次搜索返回的视频数
        self.search_order = config.config.get("search_order", "date")  # 新增：搜索排序（date/viewCount/rating）
        self.fetch_transcripts = config.config.get("fetch_transcripts", False)
        self.proxy = proxy
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                proxy=self.proxy,
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "Content-Aggregator/1.0"}
            )
        return self._client

    async def connect(self) -> bool:
        if not self.api_key:
            logger.error("YouTube API key not configured")
            return False
        # 简单测试：调用 API 验证 key 有效性
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.BASE_URL}/channels",
                params={"part": "snippet", "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw", "key": self.api_key}
            )
            if resp.status_code == 200:
                return True
            else:
                err_text = resp.text[:500]
                if looks_like_youtube_bot_challenge(err_text):
                    logger.error(f"YouTube API test failed: 可能被反机器人机制拦截 - {err_text[:200]}")
                else:
                    logger.error(f"YouTube API test failed: {resp.status_code} {err_text[:200]}")
                return False
        except Exception as e:
            logger.error(f"YouTube connect error: {e}")
            return False

    async def collect(self, filters: dict[str, Any] | None = None) -> dict:
        """
        采集配置的频道或搜索关键词的最新视频。
        返回 {success, contents: list[Content], errors: list}
        """
        if not self.api_key:
            return {"success": False, "error": "YouTube API key not configured", "contents": []}

        if not self.channels and not self.search_queries:
            return {"success": False, "error": "No YouTube channels or search queries configured", "contents": []}

        all_contents = []
        errors = []
        limit = (filters or {}).get("limit")

        # 1. 从配置的频道采集
        for ch in self.channels:
            channel_id = ch.get("channel_id", "")
            channel_name = ch.get("name", channel_id)
            max_videos = ch.get("max_videos", 10)

            if limit:
                max_videos = min(max_videos, limit)

            try:
                videos = await self._fetch_channel_videos(channel_id, max_videos)
                for video in videos:
                    content = await self._video_to_content(video, channel_name)
                    if content:
                        all_contents.append(content)
            except Exception as e:
                err_msg = f"频道 {channel_name} 采集失败: {e}"
                errors.append(err_msg)
                logger.error(err_msg)

        # 2. 从搜索关键词采集（新增）
        if self.search_queries:
            search_limit = limit or self.search_limit
            for query in self.search_queries:
                try:
                    videos = await self._search_videos(query, search_limit)
                    for video in videos:
                        content = await self._video_to_content(video, f"搜索:{query}")
                        if content:
                            all_contents.append(content)
                except Exception as e:
                    err_msg = f"搜索关键词 '{query}' 采集失败: {e}"
                    errors.append(err_msg)
                    logger.error(err_msg)

        return {
            "success": len(errors) == 0,
            "contents": all_contents,
            "errors": errors,
        }

    async def _classify_api_error(self, status_code: int, response_text: str) -> str:
        """
        分类 YouTube API 错误，返回可读的错误说明。
        """
        if status_code == 400:
            if "keyInvalid" in response_text or "badRequest" in response_text:
                return "YouTube API Key 无效，请检查 .env 中的 YOUTUBE_API_KEY"
            return f"请求参数错误: {response_text[:150]}"
        elif status_code == 403:
            if looks_like_youtube_bot_challenge(response_text):
                return ("YouTube 返回 403: 可能被反机器人机制拦截。"
                        "尝试: 1) 启用代理 2) 更换 API Key 3) 稍后再试")
            if "quotaExceeded" in response_text:
                return "YouTube API 配额已耗尽，请稍后再试（第二天配额刷新）"
            return f"YouTube API 拒绝访问 (403): {response_text[:150]}"
        elif status_code == 404:
            return "YouTube 频道/视频不存在或已删除"
        elif status_code == 429:
            return "YouTube API 速率限制，请降低采集频率"
        elif status_code >= 500:
            return "YouTube 服务端错误，可能为临时问题，请稍后再试"
        return f"YouTube API 错误 {status_code}: {response_text[:150]}"

    async def _fetch_channel_videos(self, channel_id: str, max_videos: int) -> list[dict]:
        """获取频道最新视频列表（含描述）"""
        client = await self._get_client()

        # 先获取频道标题（可选）
        resp = await client.get(
            f"{self.BASE_URL}/channels",
            params={"part": "snippet", "id": channel_id, "key": self.api_key}
        )
        if resp.status_code != 200:
            err_msg = await self._classify_api_error(resp.status_code, resp.text)
            raise Exception(err_msg)
        channel_data = resp.json()
        channel_title = channel_data["items"][0]["snippet"]["title"] if channel_data.get("items") else channel_id

        # 获取频道最新视频
        resp = await client.get(
            f"{self.BASE_URL}/search",
            params={
                "part": "snippet",
                "channelId": channel_id,
                "maxResults": max_videos,
                "order": "date",
                "type": "video",
                "key": self.api_key,
            }
        )
        if resp.status_code != 200:
            err_msg = await self._classify_api_error(resp.status_code, resp.text)
            raise Exception(err_msg)
        search_data = resp.json()
        video_items = search_data.get("items", [])

        if not video_items:
            return []

        # 批量获取视频详情（duration + viewCount）
        video_ids = [item["id"]["videoId"] for item in video_items]
        resp = await client.get(
            f"{self.BASE_URL}/videos",
            params={
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
                "key": self.api_key,
            }
        )
        if resp.status_code != 200:
            err_msg = await self._classify_api_error(resp.status_code, resp.text)
            raise Exception(err_msg)
        details_data = resp.json()

        # 合并搜索结果和详情
        details_map = {item["id"]: item for item in details_data.get("items", [])}

        results = []
        for item in video_items:
            video_id = item["id"]["videoId"]
            details = details_map.get(video_id, {})
            results.append({
                "id": video_id,
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", ""),
                "published_at": item["snippet"]["publishedAt"],
                "channel_title": channel_title,
                "channel_id": channel_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"] if item["snippet"].get("thumbnails") else "",
                "duration": details.get("contentDetails", {}).get("duration", ""),
                "view_count": details.get("statistics", {}).get("viewCount", ""),
                "details": details.get("snippet", {}),
            })
        return results

    async def _search_videos(self, query: str, max_results: int) -> list[dict]:
        """根据关键词搜索视频（使用 YouTube Data API v3），并去重"""
        client = await self._get_client()

        # 1. 加载历史记录（已采集的视频 ID）
        history_file = "data/youtube_history.json"
        collected_ids = set()
        try:
            import json
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
                collected_ids = set(history.get("collected_video_ids", []))
        except Exception:
            collected_ids = set()

        # 2. 搜索视频（按播放量排序）
        resp = await client.get(
            f"{self.BASE_URL}/search",
            params={
                "part": "snippet",
                "q": query,
                "maxResults": max_results * 2,  # 多请求一些，过滤后可能不够
                "order": self.search_order,  # 使用配置的排序方式（viewCount）
                "type": "video",
                "key": self.api_key,
            }
        )
        if resp.status_code != 200:
            err_msg = await self._classify_api_error(resp.status_code, resp.text)
            raise Exception(err_msg)
        search_data = resp.json()
        video_items = search_data.get("items", [])

        if not video_items:
            return []

        # 3. 过滤掉已采集的视频
        new_items = []
        for item in video_items:
            video_id = item["id"]["videoId"]
            if video_id not in collected_ids:
                new_items.append(item)
                if len(new_items) >= max_results:  # 只保留需要的数量
                    break

        if not new_items:
            logger.warning(f"搜索关键词 '{query}' 的所有结果都已采集过，清空历史记录后重试")
            # 清空历史记录，重新采集
            collected_ids = set()
            new_items = video_items[:max_results]
            # 更新历史文件（清空）
            try:
                import json
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump({"collected_video_ids": [], "last_collect_time": None}, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"清空历史记录失败: {e}")

        # 4. 批量获取视频详情（duration + viewCount）
        video_ids = [item["id"]["videoId"] for item in new_items]
        resp = await client.get(
            f"{self.BASE_URL}/videos",
            params={
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
                "key": self.api_key,
            }
        )
        resp.raise_for_status()
        details_data = resp.json()

        # 5. 合并搜索结果和详情
        details_map = {item["id"]: item for item in details_data.get("items", [])}

        results = []
        new_collected_ids = []
        for item in new_items:
            video_id = item["id"]["videoId"]
            details = details_map.get(video_id, {})
            results.append({
                "id": video_id,
                "title": item["snippet"]["title"],
                "description": item["snippet"].get("description", ""),
                "published_at": item["snippet"]["publishedAt"],
                "channel_title": item["snippet"]["channelTitle"],
                "channel_id": item["snippet"]["channelId"],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"] if item["snippet"].get("thumbnails") else "",
                "duration": details.get("contentDetails", {}).get("duration", ""),
                "view_count": details.get("statistics", {}).get("viewCount", ""),
                "details": details.get("snippet", {}),
            })
            new_collected_ids.append(video_id)

        # 6. 更新历史记录
        try:
            import json
            collected_ids.update(new_collected_ids)
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump({
                    "collected_video_ids": list(collected_ids),
                    "last_collect_time": datetime.now(timezone.utc).isoformat()
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"已更新 YouTube 历史记录：新增 {len(new_collected_ids)} 个视频 ID")
        except Exception as e:
            logger.error(f"更新历史记录失败: {e}")

        return results

    async def _fetch_transcript(self, video_id: str) -> str:
        """抓取视频字幕（可选功能，需安装 youtube-transcript-api）"""
        if not self.fetch_transcripts:
            return ""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            logger.warning("youtube-transcript-api not installed, skipping transcript")
            return ""

        try:
            api = YouTubeTranscriptApi()
            preferred = ["zh", "en", "zh-Hans", "zh-Hant", "en-US", "en-GB"]

            # 方法1：直接 fetch（推荐，自动尝试多种语言）
            try:
                transcript = api.fetch(video_id, languages=preferred)
                if transcript:
                    try:
                        text = "\n".join([seg.text for seg in transcript])
                    except AttributeError:
                        text = "\n".join([seg["text"] for seg in transcript])
                    if text.strip():
                        logger.info(f"[YouTube] ✅ 字幕提取成功 ({len(text)} 字)")
                        return text.strip()
            except Exception:
                pass

            # 方法1补充：任意可用字幕
            try:
                transcript = api.fetch(video_id)
                if transcript:
                    try:
                        text = "\n".join([seg.text for seg in transcript])
                    except AttributeError:
                        text = "\n".join([seg["text"] for seg in transcript])
                    if text.strip():
                        logger.info(f"[YouTube] ✅ 字幕提取成功（任意语言）({len(text)} 字)")
                        return text.strip()
            except Exception:
                pass

            # 方法2：list + fetch（精细控制）
            try:
                transcript_list = api.list(video_id)
                for lang in preferred:
                    try:
                        t = transcript_list.find_transcript([lang])
                        fetched = t.fetch()
                        try:
                            text = "\n".join([seg.text for seg in fetched])
                        except AttributeError:
                            text = "\n".join([seg["text"] for seg in fetched])
                        if text.strip():
                            return text.strip()
                    except Exception:
                        continue
                # 自动字幕
                try:
                    t = transcript_list.find_generated_transcript(preferred)
                    fetched = t.fetch()
                    try:
                        text = "\n".join([seg.text for seg in fetched])
                    except AttributeError:
                        text = "\n".join([seg["text"] for seg in fetched])
                    if text.strip():
                        return text.strip()
                except Exception:
                    pass
            except Exception:
                pass

        except Exception as e:
            logger.warning(f"Failed to fetch transcript for {video_id}: {e}")

        logger.info(f"[YouTube] ⏭ 视频 {video_id} 无可用字幕")
        return ""

    async def _video_to_content(self, video: dict, channel_name: str) -> Content | None:
        """
        将 YouTube 视频数据转为 Content 对象。

        当 fetch_transcripts=true 且视频无字幕时，跳过该视频（返回 None）。
        """
        try:
            published = video.get("published_at", "")
            if published:
                published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            else:
                published_dt = datetime.now(timezone.utc)

            # 获取正文内容
            body = ""

            if self.fetch_transcripts:
                # 启用了字幕模式：优先使用字幕
                transcript = await self._fetch_transcript(video["id"])
                if transcript:
                    body = transcript
                    content_source = "subtitle"
                    logger.info(f"[YouTube] ✅ 使用字幕: {video['id']} ({len(transcript)} 字)")
                else:
                    # 无字幕时降级到描述，不跳过
                    body = video.get("description", "")
                    content_source = "description"
                    logger.info(f"[YouTube] ⚠️ 无字幕，使用描述: {video['id']} ({len(body)} 字)")
            else:
                # 未启用字幕模式：使用视频描述
                body = video.get("description", "")
                content_source = "description"

            result = Content(
                id=f"youtube_{video['id']}",
                title=video["title"],
                content=body,
                source=f"YouTube - {channel_name}",
                author=channel_name,
                url=video["url"],
                published_at=published_dt,
                collected_at=datetime.now(timezone.utc),
                metadata={
                    "platform": "youtube",
                    "channel_id": video.get("channel_id", ""),
                    "channel_title": channel_name,
                    "video_id": video["id"],
                    "duration": video.get("duration", ""),
                    "view_count": video.get("view_count", ""),
                    "thumbnail": video.get("thumbnail", ""),
                    "transcript_source": content_source,
                },
                word_count=len(body),
                tags=[],
            )

            # 空内容保护
            if not body.strip():
                logger.warning(f"[YouTube] ⏭ {video['id']} 内容为空，跳过")
                return None

            return result
        except Exception as e:
            logger.error(f"Error converting video to Content: {e}")
            return None

    async def test(self) -> TestResult:
        """测试数据源连接"""
        ok = await self.connect()
        if ok:
            return TestResult(success=True, message="YouTube API 连接成功", details={"channels": len(self.channels)})
        else:
            return TestResult(success=False, message="YouTube API 连接失败，请检查 API Key", details={})

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
