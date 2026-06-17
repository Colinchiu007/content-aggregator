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
from typing import Optional

import requests
from content_aggregator.sources.collectors.base_collector import BaseCollector
from content_aggregator.anti_block import AntiBlockManager, create_default_manager

logger = logging.getLogger(__name__)


class XiaohongshuCollector(BaseCollector):
    """小红书笔记采集器"""

    SOURCE_NAME = "xiaohongshu"
    RATE_LIMIT = 3.0

    def __init__(self, cookie: str | None = None, xhs_token: str | None = None,
                 enable_anti_block: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.cookie = cookie
        self.xhs_token = xhs_token
        
        # 防封管理器（可选）
        self.enable_anti_block = enable_anti_block
        self.anti_block_manager: Optional[AntiBlockManager] = None
        
        if enable_anti_block:
            self.anti_block_manager = create_default_manager(enable_proxy=False)
            logger.info("[小红书] 防封采集机制已启用")

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

        # 构建请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": self.cookie or "",
            "X-s": self.xhs_token or "",
            "Referer": "https://www.xiaohongshu.com/",
        }
        
        # 发送请求（支持防封）
        if self.anti_block_manager:
            logger.info("[小红书] 使用防封管理器发送请求")
            response = await self._request_with_anti_block("GET", url, headers=headers, params=params)
        else:
            client = await self._get_client()
            response = await client.get(url, params=params, headers=headers)
        
        response.raise_for_status()
        data = response.json()
        
        if data.get("code") != 0:
            raise RuntimeError(f"小红书 API 错误: {data.get('msg', data)}")
        
        items = data.get("data", {}).get("notes", []) or data.get("items", [])

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

    async def fetch_by_url(self, url: str) -> dict:
        """
        解析单个小红书链接，返回笔记详情

        参数：
            url: 小红书笔记链接（如 https://www.xiaohongshu.com/explore/abc123）
        """
        if not self.cookie and not self.xhs_token:
            raise EnvironmentError(
                "XHS_COOKIE 未配置，请在 config.yaml 中设置 sources.xiaohongshu.cookie"
            )

        # 从 URL 提取 note_id
        import re
        match = re.search(r'xiaohongshu\.com/explore/([a-zA-Z0-9]+)', url)
        if not match:
            # 尝试匹配短链接
            match = re.search(r'xhslink\.com/([a-zA-Z0-9]+)', url)
            if not match:
                raise ValueError(f"无法从小红书链接提取 note_id: {url}")
            # 短链接需要先解析（TODO: 实现短链接解析）
            raise NotImplementedError("暂不支持小红书短链接，请使用完整链接")

        note_id = match.group(1)

        # 构建请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": self.cookie or "",
            "X-s": self.xhs_token or "",
            "Referer": "https://www.xiaohongshu.com/",
        }
        
        # 发送请求（支持防封）
        if self.anti_block_manager:
            logger.info("[小红书] 使用防封管理器发送请求（fetch_by_url）")
            response = await self._request_with_anti_block("GET", api_url, headers=headers, params=params)
        else:
            client = await self._get_client()
            response = await client.get(api_url, params=params, headers=headers)
        
        response.raise_for_status()
        params = {
            "note_id": note_id,
            "image_scenes": "MAIN",
        }

        response = await client.get(api_url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise RuntimeError(f"小红书 API 错误: {data.get('msg', data)}")

        note_card = data.get("data", {}).get("note", {})
        if not note_card:
            raise RuntimeError(f"小红书笔记不存在或无权限访问: {note_id}")

        author = note_card.get("user", {})

        published_str = note_card.get("time", "") or note_card.get("created_at", "")
        published = None
        if published_str:
            try:
                published = datetime.fromtimestamp(int(published_str))
            except Exception:
                try:
                    published = datetime.fromisoformat(published_str).replace(tzinfo=None)
                except Exception:
                    pass

        # 判断媒体类型
        media_type = "image_text"
        if note_card.get("type") == "video":
            media_type = "video"

        return {
            "title": note_card.get("display_title", "") or note_card.get("title", "") or "",
            "content": note_card.get("desc", "") or "",
            "url": f"https://www.xiaohongshu.com/explore/{note_id}",
            "author": author.get("nickname", "") or "",
            "published_at": published,
            "summary": note_card.get("desc", "")[:300] or "",
            "tags": note_card.get("tag_list", []) or [],
            "source": self.SOURCE_NAME,
            "media_type": media_type,
            "original_text": note_card.get("desc", "") or "",
            "transcribed_text": "",  # 视频才有，需要 ASR
            "metadata": {
                "note_id": note_id,
                "type": note_card.get("type", ""),
                "likes": note_card.get("interact_info", {}).get("liked_count", 0),
                "video_url": note_card.get("video", {}).get("url", "") if media_type == "video" else "",
            }
        }

    @staticmethod
    def detect_platform(url: str) -> bool:
        """判断 URL 是否属于小红书"""
        return "xiaohongshu.com" in url or "xhslink.com" in url
    
    async def _request_with_anti_block(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        使用防封管理器发送请求
        
        注意：防封管理器返回的是同步 Response，需要适配异步上下文
        """
        if not self.anti_block_manager:
            raise RuntimeError("防封管理器未初始化")
        
        # 防封管理器是同步的，需要在异步上下文中运行
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.anti_block_manager.request(method, url, **kwargs)
        )
        
        return response
    
    def enable_anti_block_feature(self, manager: Optional[AntiBlockManager] = None):
        """启用防封功能"""
        if manager:
            self.anti_block_manager = manager
        elif not self.anti_block_manager:
            self.anti_block_manager = create_default_manager(enable_proxy=False)
        
        self.enable_anti_block = True
        logger.info("[小红书] 防封采集机制已启用")
    
    def disable_anti_block_feature(self):
        """禁用防封功能"""
        self.enable_anti_block = False
        logger.info("[小红书] 防封采集机制已禁用")
    
    def get_anti_block_stats(self) -> dict:
        """获取防封统计信息"""
        if self.anti_block_manager:
            return self.anti_block_manager.get_stats()
        return {"enabled": False}