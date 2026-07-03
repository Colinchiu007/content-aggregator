"""
微博热点（热搜榜）采集器

微博热搜接口：https://weibo.com/ajax/side/hotSearch
- 免登录即可访问
- 返回实时热搜榜（通常 50 条）

注意：
- 微博接口返回的是话题/关键词，不是完整文章
- 需要二次搜索获取相关文章链接
- 每条热搜包含：rank(排名)、word(关键词)、flag(热度标识: 新/热/爆)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult
from content_aggregator.anti_block import AntiBlockManager, create_default_manager

logger = logging.getLogger(__name__)


class WeiboHotCollector(BaseCollector):
    """微博热点采集器"""

    SOURCE_NAME = "weibo_hot"
    RATE_LIMIT = 5.0  # 微博反爬较严

    # 热搜榜 API
    HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch"

    # 热搜详情页（微博话题页）
    TOPIC_URL_TEMPLATE = "https://s.weibo.com/top/summary"

    def __init__(
        self,
        proxy: str | None = None,
        timeout: int = 30,
        config: dict | None = None,
        enable_anti_block: bool = False,
        **kwargs,
    ):
        super().__init__(proxy=proxy, timeout=timeout, config=config, **kwargs)
        self.limit = self.config.get("limit", 30)  # 默认取前30条
        self.include_detail = self.config.get("include_detail", False)  # 是否获取详情页链接
        self.enable_anti_block = enable_anti_block
        self.anti_block_manager: AntiBlockManager | None = None

        if enable_anti_block:
            self.anti_block_manager = create_default_manager(enable_proxy=proxy is not None)
            logger.info("[微博热点] 防封采集机制已启用")

    async def _fetch(self, **kwargs) -> list[dict]:
        """采集微博热搜榜"""
        import time
        start = time.time()

        # 1. 获取热搜列表
        hot_list = await self._fetch_hot_search_list()
        if not hot_list:
            return []

        logger.info(f"[微博热点] 获取到 {len(hot_list)} 条热搜")

        # 2. 截取前 N 条
        if self.limit > 0:
            hot_list = hot_list[: self.limit]

        # 3. 可选：获取每条热搜的真实微博内容
        if self.include_detail:
            logger.info("[微博热点] 正在获取热搜相关微博内容...")
            for item in hot_list:
                try:
                    articles = await self.fetch_topic_articles(item["word"], limit=3)
                    if articles:
                        # 取前几篇微博拼接为正文
                        contents = [a.get("content", "") for a in articles[:3]]
                        item["content"] = "\n\n".join(contents)
                        item["url"] = articles[0].get("url", item.get("url", ""))
                    await asyncio.sleep(1)  # 限流
                except Exception as e:
                    logger.warning(f"[微博热点] 获取 {item['word']} 微博内容失败: {e}")

        logger.info(f"[微博热点] 采集完成，共 {len(hot_list)} 条")
        return hot_list

    async def _fetch_hot_search_list(self) -> list[dict]:
        """获取微博热搜榜"""
        if self.enable_anti_block and self.anti_block_manager:
            return await self._fetch_with_anti_block()
        else:
            return await self._fetch_normal()

    async def _fetch_normal(self) -> list[dict]:
        """普通模式获取热搜"""
        client = await self._get_client()
        await self._rate_limit_wait()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://weibo.com/",
            "X-Requested-With": "XMLHttpRequest",
        }

        response = await client.get(self.HOT_SEARCH_URL, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data.get("data"):
            logger.warning("[微博热点] 返回数据为空")
            return []

        real_data = data["data"].get("realtime", [])
        if not real_data:
            logger.warning("[微博热点] realtime 列表为空")
            return []

        results = []
        for item in real_data:
            rank = item.get("num", 0)
            word = item.get("word", "")
            flag = item.get("flag", 0)  # 0=普通, 1=新, 2=热, 3=爆

            # 热度标识
            heat_label = {0: "", 1: "新", 2: "热", 3: "爆"}.get(flag, "")

            # 跳过广告（flag=4 通常是广告）
            if flag == 4:
                continue

            results.append({
                "title": word,
                "content": word,
                "title": word,
                "url": f"https://s.weibo.com/weibo?q={word}",  # 搜索结果页
                "source": self.SOURCE_NAME,
                "rank": rank,
                "heat_label": heat_label,
                "word": word,
                "published_at": datetime.now(),
                "summary": f"微博热搜第{rank}名{heat_label and f'（{heat_label}）' or ''}",
                "metadata": {
                    "rank": rank,
                    "flag": flag,
                    "heat_label": heat_label,
                },
            })

        return results

    async def _fetch_with_anti_block(self) -> list[dict]:
        """防封模式获取热搜"""
        import asyncio
        loop = asyncio.get_event_loop()

        def _do_fetch():
            return self.anti_block_manager.request("GET", self.HOT_SEARCH_URL, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://weibo.com/",
            })

        response = await loop.run_in_executor(None, _do_fetch)
        import json
        data = json.loads(response.text)

        if not data.get("data"):
            return []

        real_data = data["data"].get("realtime", [])
        results = []
        for item in real_data:
            rank = item.get("num", 0)
            word = item.get("word", "")
            flag = item.get("flag", 0)

            if flag == 4:
                continue

            heat_label = {0: "", 1: "新", 2: "热", 3: "爆"}.get(flag, "")

            results.append({
                "title": word,
                "content": word,
                "title": word,
                "url": f"https://s.weibo.com/weibo?q={word}",
                "source": self.SOURCE_NAME,
                "rank": rank,
                "heat_label": heat_label,
                "word": word,
                "published_at": datetime.now(),
                "summary": f"微博热搜第{rank}名{heat_label and f'（{heat_label}）' or ''}",
                "metadata": {"rank": rank, "flag": flag, "heat_label": heat_label},
            })

        return results

    async def _get_topic_detail_url(self, word: str) -> str:
        """获取微博话题详情页 URL"""
        import urllib.parse
        encoded = urllib.parse.quote(word)
        return f"https://s.weibo.com/top/summary?cate={encoded}"

    async def fetch_topic_articles(self, word: str, limit: int = 10) -> list[dict]:
        """
        搜索某条热搜关键词下的相关文章

        注意：这需要登录 Cookie 才能获取较好的结果
        """
        import urllib.parse

        encoded = urllib.parse.quote(word)
        search_url = f"https://s.weibo.com/weibo?q={encoded}&topnav=1&wvr=6"

        client = await self._get_client()
        await self._rate_limit_wait()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            response = await client.get(search_url, headers=headers)
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"[微博热点] 搜索 {word} 失败: {e}")
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        articles = []
        # 微博搜索结果页结构：每条微博在 .card-wrap 中
        for card in soup.select(".card-wrap"):
            # 提取微博正文
            content_div = card.select_one(".txt")
            if not content_div:
                continue

            content = content_div.get_text(strip=True)
            if len(content) < 10:
                continue

            # 提取链接
            link_tag = card.select_one("a[href*='weibo.com/detail']")
            url = link_tag["href"] if link_tag else ""
            if not url.startswith("http"):
                url = f"https://weibo.com{url}"

            # 提取发布时间
            time_tag = card.select_one(".from")
            published_at = None
            if time_tag:
                time_text = time_tag.get_text(strip=True)
                published_at = self._parse_weibo_time(time_text)

            articles.append({
                "title": content[:100],
                "content": content,
                "url": url,
                "source": self.SOURCE_NAME,
                "published_at": published_at,
                "metadata": {"search_keyword": word},
            })

            if len(articles) >= limit:
                break

        return articles

    def _parse_weibo_time(self, time_text: str) -> datetime | None:
        """解析微博时间文本"""
        from datetime import timedelta

        time_text = time_text.strip()

        # "刚刚"
        if "刚刚" in time_text:
            return datetime.now()

        # "X分钟前"
        import re
        match = re.search(r"(\d+)分钟前", time_text)
        if match:
            minutes = int(match.group(1))
            return datetime.now() - timedelta(minutes=minutes)

        # "X小时前"
        match = re.search(r"(\d+)小时前", time_text)
        if match:
            hours = int(match.group(1))
            return datetime.now() - timedelta(hours=hours)

        # "昨天"
        if "昨天" in time_text:
            return datetime.now() - timedelta(days=1)

        # "MM-DD" 格式
        match = re.search(r"(\d{1,2})-(\d{1,2})", time_text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            return datetime(datetime.now().year, month, day)

        return None
