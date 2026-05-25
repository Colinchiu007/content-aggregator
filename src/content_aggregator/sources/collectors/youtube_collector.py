"""
YouTube 采集器

支持：
- 频道最新视频列表（通过 YouTube Data API v3）
- 播放列表视频列表
- 视频字幕提取（优先自动字幕 → 手动字幕 → AI 识别）

注意：需要 YouTube Data API Key（免费额度：每天 10000 单位）
无代理/无 API Key 时跳过采集并给出提示，不中断流程。
"""

import logging
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult

logger = logging.getLogger(__name__)

# 延迟导入，避免顶层报错（未安装库时不破坏初始化）
_transcript_api = None


def _get_transcript_api():
    """懒加载字幕提取库"""
    global _transcript_api
    if _transcript_api is None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            _transcript_api = YouTubeTranscriptApi
        except ImportError:
            logger.warning("[YouTube] 未安装 youtube-transcript-api，字幕提取不可用")
            _transcript_api = False
    return _transcript_api


class YouTubeCollector(BaseCollector):
    """YouTube 频道视频采集器"""

    SOURCE_NAME = "youtube"
    RATE_LIMIT = 3.0

    def __init__(self, api_key: str | None = None, fetch_transcript: bool = True,
                 llm_config: dict | None = None, **kwargs):
        """
        参数：
            api_key: YouTube Data API Key
            fetch_transcript: 是否提取字幕（默认 True）
            llm_config: LLM 配置（用于无字幕时 AI 识别）
                - api_key: API 密钥
                - model: 模型名（如 deepseek-v4-pro）
                - base_url: API 地址
        """
        super().__init__(**kwargs)
        self.api_key = api_key
        self.fetch_transcript = fetch_transcript
        self.llm_config = llm_config or {}

    async def collect(self, **kwargs) -> SourceResult:
        """Implement BaseCollector.collect, map max_items to max_results"""
        if 'max_items' in kwargs:
            kwargs['max_results'] = kwargs.pop('max_items')
        if 'base_url' in kwargs and 'channel_id' not in kwargs:
            import re as _re
            bu = kwargs.pop("base_url")
            uc = _re.search(r"UC[\w-]{22}", bu)
            if uc:
                kwargs['channel_id'] = uc.group()
            else:
                kwargs["channel_id"] = bu
        try:
            data = await self._fetch(**kwargs)
            return SourceResult(success=True, data=data, error=None, source_name=self.SOURCE_NAME, collected_count=len(data))
        except Exception as e:
            logger.error(f"collect failed: {e}")
            return SourceResult(success=False, data=[], error=str(e), source_name=self.SOURCE_NAME)

    async def _fetch(self, channel_id: str | None = None, playlist_id: str | None = None,
                     max_results: int = 20, search_query: str | None = None,
                     order: str = "date", **kwargs) -> list[dict]:
        """
        采集 YouTube 视频

        参数：
            channel_id: YouTube 频道 ID（如 UC...）
            playlist_id: 播放列表 ID（如 LL... 用于获取频道最新视频）
            max_results: 最大条数
            search_query: 搜索关键词（如 "AI agent"）
            order: 排序方式 - date（更新时间）、viewCount（播放量）、relevance（相关度）
        """
        if not self.api_key:
            raise EnvironmentError("YOUTUBE_API_KEY 未配置，请在 config.yaml 中设置 sources.youtube.api_key")

        channel_id = channel_id or self.config.get("channel_id")
        playlist_id = playlist_id or self.config.get("playlist_id")
        search_query = search_query or self.config.get("search_query")
        order = order or self.config.get("order", "date")

        if not channel_id and not playlist_id and not search_query:
            raise ValueError("YouTube 采集器需要 channel_id、playlist_id 或 search_query 参数")

        # 构建 API URL
        if search_query:
            # 关键词搜索模式
            base_url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": search_query,
                "type": "video",
                "order": order,
                "maxResults": min(max_results, 50),
                "key": self.api_key,
            }
        elif playlist_id:
            base_url = "https://www.googleapis.com/youtube/v3/playlistItems"
            params = {
                "part": "snippet",
                "playlistId": playlist_id,
                "maxResults": min(max_results, 50),
                "key": self.api_key,
            }
        else:
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
        response = await client.get(base_url, params=params)
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

            # 默认内容：标题 + 描述
            title = snippet.get("title", "") or ""
            description = snippet.get("description", "") or ""
            content_text = description

            # 提取字幕（如需要）
            if self.fetch_transcript and video_id:
                transcript = await self._get_transcript(video_id)
                if transcript:
                    content_text = transcript  # 字幕优先
                    logger.info(f"[YouTube] 视频 {video_id} 字幕提取成功 ({len(transcript)} 字)")

            results.append({
                "title": title,
                "content": content_text,  # 字幕 > 描述
                "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                "author": snippet.get("channelTitle", "") or "",
                "published_at": published,
                "summary": description[:500] or "",
                "tags": [],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "video_id": video_id,
                    "channel_id": snippet.get("channelId", "") or "",
                    "thumbnails": snippet.get("thumbnails", {}),
                    "transcript_source": "subtitle" if content_text != description else "description",
                }
            })

        logger.info(f"[YouTube] 采集到 {len(results)} 个视频")
        return results

    async def _get_transcript(self, video_id: str) -> str | None:
        """
        获取视频字幕文本

        优先级：
        1. 手动字幕（已翻译）
        2. 自动字幕
        3. 描述（fallback，已在调用处处理）
        """
        api = _get_transcript_api()
        if not api:
            return None

        try:
            # 优先获取中文/英文自动字幕，按语言优先级列表尝试
            transcript_list = api.list_transcripts(video_id)

            # 语言优先级：中文 -> 英文 -> 其他
            preferred_langs = ["zh", "en", "zh-Hans", "zh-Hant", "en-US", "en-GB"]

            for lang in preferred_langs:
                try:
                    # 尝试查找该语言的手动字幕
                    transcript = transcript_list.find_transcript([lang])
                    text = " ".join([seg["text"] for seg in transcript.fetch()])
                    if text.strip():
                        return text.strip()
                except Exception:
                    continue

            # 自动字幕（降级）
            try:
                transcript = transcript_list.find_generated_transcript(preferred_langs)
                text = " ".join([seg["text"] for seg in transcript.fetch()])
                if text.strip():
                    return text.strip()
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"[YouTube] 视频 {video_id} 字幕提取失败: {e}")

        return None

    async def _transcribe_with_llm(self, video_id: str) -> str | None:
        """
        无字幕时调用 LLM 进行语音识别（需要视频下载 + ASR，暂未实现）
        未来可接入 Whisper 等本地模型。
        """
        # 占位实现：需要视频下载 -> 音频 -> Whisper API
        # 目前返回 None，依赖描述作为 fallback
        return None