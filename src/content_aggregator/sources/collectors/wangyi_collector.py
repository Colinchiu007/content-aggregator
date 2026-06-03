"""
网易新闻采集器

移植自 article-spider (https://github.com/Anning01/article-spider)
适配 PROJECT-001 的 BaseCollector 接口

支持频道：
- 新闻 (news)
- 娱乐 (ent)
- 科技 (tech)
- 体育 (sports)
- 财经 (finance)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult
from content_aggregator.anti_block import AntiBlockManager, create_default_manager

logger = logging.getLogger(__name__)


class WangYiCollector(BaseCollector):
    """网易新闻采集器"""

    SOURCE_NAME = "wangyi"
    RATE_LIMIT = 3.0  # 网易反爬较严，间隔拉长

    # 频道映射
    CHANNELS = {
        "news": "新闻",
        "ent": "娱乐",
        "tech": "科技",
        "sports": "体育",
        "finance": "财经",
    }

    # 各频道列表页 URL 模板
    CHANNEL_URLS = {
        "news": "https://news.163.com/",
        "ent": "https://ent.163.com/",
        "tech": "https://tech.163.com/",
        "sports": "https://sports.163.com/",
        "finance": "https://money.163.com/",
    }

    def __init__(
        self,
        proxy: str | None = None,
        timeout: int = 30,
        config: dict | None = None,
        enable_anti_block: bool = False,
        **kwargs,
    ):
        super().__init__(proxy=proxy, timeout=timeout, config=config, **kwargs)
        self.channels = self.config.get("channels", ["news", "ent", "tech"])
        self.limit = self.config.get("limit", 10)
        self.enable_anti_block = enable_anti_block
        self.anti_block_manager: AntiBlockManager | None = None

        if enable_anti_block:
            self.anti_block_manager = create_default_manager(enable_proxy=proxy is not None)
            logger.info("[网易新闻] 防封采集机制已启用")

    async def _fetch(self, **kwargs) -> list[dict]:
        """采集网易新闻"""
        import time
        start = time.time()

        results: list[dict] = []
        channels_to_fetch = kwargs.get("channels", self.channels)

        for channel in channels_to_fetch:
            if channel not in self.CHANNEL_URLS:
                logger.warning(f"[网易新闻] 未知频道: {channel}，跳过")
                continue

            list_url = self.CHANNEL_URLS[channel]
            logger.info(f"[网易新闻] 开始采集频道: {self.CHANNELS.get(channel, channel)} ({list_url})")

            try:
                articles = await self._fetch_channel(channel, list_url)
                results.extend(articles)
                logger.info(f"[网易新闻] 频道 {channel} 采集到 {len(articles)} 篇文章")
            except Exception as e:
                logger.warning(f"[网易新闻] 频道 {channel} 采集失败: {e}")

        # 去重（按 URL）
        seen_urls: set[str] = set()
        deduped: list[dict] = []
        for article in results:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(article)

        if self.limit > 0:
            deduped = deduped[: self.limit]

        logger.info(f"[网易新闻] 总计采集 {len(deduped)} 篇（去重后）")
        return deduped

    async def _fetch_channel(self, channel: str, list_url: str) -> list[dict]:
        """采集单个频道"""
        if self.enable_anti_block and self.anti_block_manager:
            return await self._fetch_channel_anti_block(channel, list_url)
        else:
            return await self._fetch_channel_normal(channel, list_url)

    async def _fetch_channel_normal(self, channel: str, list_url: str) -> list[dict]:
        """普通模式采集频道"""
        client = await self._get_client()
        await self._rate_limit_wait()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        response = await client.get(list_url, headers=headers)
        response.raise_for_status()
        html = response.text

        return self._parse_list_html(html, channel)

    async def _fetch_channel_anti_block(self, channel: str, list_url: str) -> list[dict]:
        """防封模式采集频道"""
        import asyncio
        loop = asyncio.get_event_loop()

        def _do_fetch():
            return self.anti_block_manager.request("GET", list_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })

        response = await loop.run_in_executor(None, _do_fetch)
        html = response.text
        return self._parse_list_html(html, channel)

    def _parse_list_html(self, html: str, channel: str) -> list[dict]:
        """解析列表页 HTML，提取文章链接"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict] = []

        # 网易新闻列表页结构：每个文章在 .news-item 或 .n-item 容器中
        # 不同频道结构略有差异，尝试多种选择器

        # 方法1: 查找所有 <h3> 或 <h2> 中的链接（网易常用结构）
        for h_tag in soup.find_all(["h3", "h2"]):
            link_tag = h_tag.find("a")
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            if not title or len(title) < 3:
                continue

            href = link_tag.get("href", "")
            if not href or "163.com" not in href:
                continue

            # 提取发布时间
            published_at = self._extract_publish_time(h_tag)

            articles.append({
                "title": title,
                "url": href,
                "source": self.SOURCE_NAME,
                "channel": self.CHANNELS.get(channel, channel),
                "published_at": published_at,
                "metadata": {"fetch_method": "list_page"},
            })

        # 方法2: 查找 .news-item 容器
        if not articles:
            for item in soup.select(".news-item, .n-item, .article-item"):
                link_tag = item.find("a", href=True)
                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                if not title or len(title) < 3:
                    continue

                href = link_tag["href"]
                if "163.com" not in href:
                    continue

                published_at = self._extract_publish_time(item)

                articles.append({
                    "title": title,
                    "url": href,
                    "source": self.SOURCE_NAME,
                    "channel": self.CHANNELS.get(channel, channel),
                    "published_at": published_at,
                    "metadata": {"fetch_method": "news_item"},
                })

        # 方法3: 查找所有含 163.com 的文章链接（兜底）
        if not articles:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "163.com" not in href or href.endswith(".html"):
                    continue

                title = a_tag.get_text(strip=True)
                if not title or len(title) < 3 or len(title) > 200:
                    continue

                published_at = self._extract_publish_time(a_tag)

                articles.append({
                    "title": title,
                    "url": href,
                    "source": self.SOURCE_NAME,
                    "channel": self.CHANNELS.get(channel, channel),
                    "published_at": published_at,
                    "metadata": {"fetch_method": "fallback"},
                })

        return articles

    def _extract_publish_time(self, element) -> datetime | None:
        """从元素中提取发布时间"""
        import re

        # 查找时间相关的标签或属性
        time_patterns = [
            r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",  # 2024-01-15
            r"(\d{1,2})月(\d{1,2})日",               # 1月15日
        ]

        text = element.get_text()

        for pattern in time_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if "月" in pattern:
                        year = datetime.now().year
                        month = int(match.group(1))
                        day = int(match.group(2))
                    else:
                        year = int(match.group(1))
                        month = int(match.group(2))
                        day = int(match.group(3))

                    if 1990 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
                except ValueError:
                    pass

        return None

    async def fetch_article_detail(self, url: str) -> dict | None:
        """
        获取单篇文章详情（用于采集后补充完整内容）

        网易新闻详情页结构相对固定，可以提取完整正文
        """
        client = await self._get_client()
        await self._rate_limit_wait()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.warning(f"[网易新闻] 获取详情页失败 {url}: {e}")
            return None

        return self._parse_detail_html(html, url)

    def _parse_detail_html(self, html: str, url: str) -> dict | None:
        """解析详情页 HTML，提取完整文章"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # 提取标题
        title = ""
        if soup.title:
            title = soup.title.string or ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]

        if not title:
            return None

        # 提取正文 - 网易文章正文通常在 #artibody 或 .article 中
        content = ""
        for selector in ["#artibody", ".article", ".article-body", "#content"]:
            element = soup.select_one(selector)
            if element:
                content = element.get_text(separator="\n", strip=True)
                break

        # 兜底：取所有 <p> 标签
        if not content:
            paragraphs = soup.find_all("p")
            content = "\n".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 10)

        # 提取作者
        author = ""
        author_tag = soup.find("meta", attrs={"name": "author"})
        if author_tag and author_tag.get("content"):
            author = author_tag["content"]

        # 提取发布时间
        published_at = None
        time_tag = soup.find("meta", property="article:published_time")
        if time_tag and time_tag.get("content"):
            try:
                published_at = datetime.fromisoformat(time_tag["content"].replace("Z", "+00:00"))
            except Exception:
                pass

        if not published_at:
            # 尝试从页面文本提取
            import re
            text = soup.get_text()
            match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
            if match:
                try:
                    published_at = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
                except ValueError:
                    pass

        return {
            "title": title,
            "content": content,
            "url": url,
            "source": self.SOURCE_NAME,
            "author": author,
            "published_at": published_at,
            "summary": content[:300] if content else title,
        }
