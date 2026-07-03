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
from typing import Optional

import requests
from content_aggregator.sources.collectors.base_collector import BaseCollector
from content_aggregator.anti_block import AntiBlockManager, create_default_manager

logger = logging.getLogger(__name__)


class DouyinCollector(BaseCollector):
    """抖音国内版采集器"""

    SOURCE_NAME = "douyin"
    RATE_LIMIT = 3.0

    def __init__(self, cookie: str | None = None, client_key: str | None = None,
                 enable_anti_block: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.cookie = cookie
        self.client_key = client_key
        
        # 防封管理器（可选）
        self.enable_anti_block = enable_anti_block
        self.anti_block_manager: Optional[AntiBlockManager] = None
        
        if enable_anti_block:
            self.anti_block_manager = create_default_manager(enable_proxy=False)
            logger.info("[抖音] 防封采集机制已启用")

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

        # 构建请求头
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        if self.cookie:
            headers["Cookie"] = self.cookie
        
        # 发送请求（支持防封）
        if self.anti_block_manager:
            logger.info("[抖音] 使用防封管理器发送请求")
            try:
                response = await self._request_with_anti_block("GET", url, headers=headers, params=params)
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
                response = await self._request_with_anti_block("GET", url2, headers=headers, params=params2)
        else:
            # 原有逻辑
            client = await self._get_client()
            try:
                response = await client.get(url, params=params, headers=headers)
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
                response = await client.get(url2, params=params2, headers=headers)
        
        response.raise_for_status()

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

    async def fetch_by_url(self, url: str) -> dict:
        """
        解析单个抖音链接，返回视频详情

        参数：
            url: 抖音视频链接（如 https://www.douyin.com/video/abc123）
        """
        if not self.cookie and not self.client_key:
            raise EnvironmentError(
                "DOUYIN_COOKIE 或 DOUYIN_CLIENT_KEY 未配置，请在 config.yaml 中设置"
            )

        # 从 URL 提取 aweme_id
        import re
        match = re.search(r'douyin\.com/video/([0-9]+)', url)
        if not match:
            match = re.search(r'iesdouyin\.com/share/video/([0-9]+)', url)
            if not match:
                raise ValueError(f"无法从抖音链接提取 aweme_id: {url}")

        aweme_id = match.group(1)

        # 构建请求头
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        if self.cookie:
            headers["Cookie"] = self.cookie
        
        # 调用 API 获取单个视频详情
        api_url = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
        params = {
            "aweme_id": aweme_id,
            "cookie_enabled": 1,
            "platform": "PC",
            "downlink": 10,
        }
        
        # 发送请求（支持防封）
        if self.anti_block_manager:
            logger.info("[抖音] 使用防封管理器发送请求（fetch_by_url）")
            response = await self._request_with_anti_block("GET", api_url, headers=headers, params=params)
        else:
            client = await self._get_client()
            response = await client.get(api_url, params=params, headers=headers)
        
        response.raise_for_status()
        data = response.json()

        aweme_list = data.get("aweme_detail", {}) or data.get("awemeData", {})
        if not aweme_list:
            raise RuntimeError(f"抖音视频不存在或无权限访问: {aweme_id}")

        item = aweme_list if isinstance(aweme_list, dict) else aweme_list[0]
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

        # 获取视频播放地址（需要转写时用）
        video_url = ""
        if video_info:
            # 尝试获取无水印视频地址
            play_addr = video_info.get("play_addr", {}).get("url_list", [])
            if play_addr:
                video_url = play_addr[0]

        return {
            "title": item.get("desc", "") or "",
            "content": item.get("desc", "") or "",
            "url": f"https://www.douyin.com/video/{aweme_id}",
            "author": author.get("nickname", "") or author.get("unique_id", "") or "",
            "published_at": published,
            "summary": item.get("desc", "")[:300] or "",
            "tags": [t.get("hashtag_name", "") for t in item.get("text_extra", [])],
            "source": self.SOURCE_NAME,
            "media_type": "video",
            "original_text": item.get("desc", "") or "",
            "transcribed_text": "",  # 需要 ASR
            "metadata": {
                "aweme_id": aweme_id,
                "likes": stats.get("digg_count", 0),
                "views": stats.get("play_count", 0),
                "comments": stats.get("comment_count", 0),
                "video_url": video_url,  # 用于下载后 ASR
            }
        }

    @staticmethod
    def detect_platform(url: str) -> bool:
        """判断 URL 是否属于抖音"""
        return "douyin.com" in url or "iesdouyin.com" in url
    
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
        logger.info("[抖音] 防封采集机制已启用")
    
    def disable_anti_block_feature(self):
        """禁用防封功能"""
        self.enable_anti_block = False
        logger.info("[抖音] 防封采集机制已禁用")
    
    def get_anti_block_stats(self) -> dict:
        """获取防封统计信息"""
        if self.anti_block_manager:
            return self.anti_block_manager.get_stats()
        return {"enabled": False}