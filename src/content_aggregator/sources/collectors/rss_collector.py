"""
RSS 采集器

支持标准 RSS/Atom 格式输入，自动检测格式。

标准化字段：
    title, content, url, author, published_at, summary, tags, source
"""

import feedparser
import logging
from datetime import datetime
from typing import Any

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """RSS/Atom 采集器"""

    SOURCE_NAME = "rss"
    RATE_LIMIT = 1.0   # RSS 请求间隔可以短一些

    async def _fetch(self, url: str | None = None, max_items: int = 20, **kwargs) -> list[dict]:
        """
        采集 RSS 源

        参数：
            url: RSS 链接（优先）或从 self.config 获取
            max_items: 最大采集条数
        """
        import httpx

        # 获取客户端（可能已关闭）
        client = await self._get_client()

        target_url = url or self.config.get("url")
        if not target_url:
            raise ValueError("RSS 采集器缺少 URL 参数")

        logger.info(f"[RSS] 采集: {target_url}")

        # 发起请求
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ContentAggregator/1.0)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        }

        response = await client.get(target_url, headers=headers, proxy=self.proxy)
        response.raise_for_status()

        # 解析
        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS 解析失败：{feed.bozo_exception}")

        results = []
        for entry in feed.entries[:max_items]:
            article = self._parse_entry(entry, feed.feed)
            results.append(article)

        logger.info(f"[RSS] 采集到 {len(results)} 篇")
        return results

    def _parse_entry(self, entry: Any, feed: Any) -> dict:
        """解析单条 RSS 条目为标准字典"""
        # 发布时间
        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                pass

        # 内容（优先 fullcontent，其次 content[0]，最后 summary）
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].value
        elif hasattr(entry, "summary"):
            content = entry.summary
        elif hasattr(entry, "description"):
            content = entry.description

        # 清理 HTML
        content = self._strip_html(content)

        # 标签
        tags = []
        if hasattr(entry, "tags"):
            tags = [t.term for t in entry.tags]

        return {
            "title": getattr(entry, "title", "") or "",
            "content": content,
            "url": getattr(entry, "link", "") or getattr(entry, "id", "") or "",
            "author": getattr(entry, "author", "") or getattr(feed, "author", "") or "",
            "published_at": published,
            "summary": getattr(entry, "summary", "") or "",
            "tags": tags,
            "source": self.SOURCE_NAME,
            "metadata": {
                "feed_title": getattr(feed, "title", "") or "",
                "feed_url": getattr(feed, "link", "") or "",
            }
        }

    def _strip_html(self, html: str) -> str:
        """去除 HTML 标签"""
        from bs4 import BeautifulSoup
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)