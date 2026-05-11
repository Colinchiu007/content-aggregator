"""
RSS 采集器

使用方法:
    from collector import RSSCollector

    collector = RSSCollector("https://www.ruanyifeng.com/blog/atom.xml")
    result = collector.collect()

    if result["success"]:
        for article in result["data"]:
            print(article["title"], article["url"])
"""

import asyncio
import feedparser
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid
import httpx
from bs4 import BeautifulSoup


@dataclass
class Article:
    """单篇文章"""
    title: str
    content: str
    url: str
    author: str = ""
    published_at: datetime | None = None
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "summary": self.summary,
            "tags": self.tags,
            "source": self.source,
        }


@dataclass
class CollectorConfig:
    """采集配置"""
    url: str
    timeout: int = 30
    max_items: int = 20
    proxy: str | None = None


class RSSCollector:
    """
    RSS 采集器

    独立模块，从 RSS/Atom 源采集文章。

    使用示例:
        collector = RSSCollector("https://example.com/rss.xml")
        result = collector.collect()

        # result = {
        #     "success": True,
        #     "data": [Article, ...],
        #     "count": 10,
        #     "error": None
        # }
    """

    def __init__(self, url: str, **kwargs):
        """
        初始化采集器

        Args:
            url: RSS URL
            **kwargs: 配置参数（timeout, max_items, proxy）
        """
        self.config = CollectorConfig(url=url, **kwargs)

    def collect(self) -> dict[str, Any]:
        """
        采集文章（同步方法）

        Returns:
            {
                "success": bool,
                "data": list[Article],
                "count": int,
                "error": str | None
            }
        """
        try:
            feed = self._fetch_feed()
            articles = self._parse_entries(feed)
            return {
                "success": True,
                "data": articles,
                "count": len(articles),
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "count": 0,
                "error": str(e)
            }

    async def collect_async(self) -> dict[str, Any]:
        """
        采集文章（异步方法）

        Returns:
            同 collect()
        """
        loop = asyncio.get_event_loop()
        try:
            feed = await self._fetch_feed_async()
            articles = self._parse_entries(feed)
            return {
                "success": True,
                "data": articles,
                "count": len(articles),
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "count": 0,
                "error": str(e)
            }

    def _fetch_feed(self) -> feedparser.FeedParserDict:
        """同步获取 RSS（无代理）"""
        return feedparser.parse(self.config.url)

    async def _fetch_feed_async(self) -> feedparser.FeedParserDict:
        """异步获取 RSS（支持代理）"""
        loop = asyncio.get_event_loop()

        try:
            async with httpx.AsyncClient(
                timeout=float(self.config.timeout),
                follow_redirects=True,
                proxy=self.config.proxy
            ) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = await client.get(self.config.url, headers=headers)
                response.raise_for_status()
                feed_data = response.text
        except Exception:
            # Fallback: 无代理直连
            feed_data = None

        if feed_data is None:
            return await loop.run_in_executor(None, feedparser.parse, self.config.url)

        return await loop.run_in_executor(None, feedparser.parse, feed_data)

    def _parse_entries(self, feed: feedparser.FeedParserDict) -> list[Article]:
        """解析 RSS 条目为 Article 列表"""
        articles = []
        feed_title = feed.feed.get("title", self.config.url)

        for entry in feed.entries[:self.config.max_items]:
            try:
                # 解析日期
                published_at = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published_at = datetime(*entry.published_parsed[:6])

                # 获取正文
                content_text = ""
                if hasattr(entry, "content") and entry.content:
                    content_text = entry.content[0].value
                elif hasattr(entry, "summary"):
                    content_text = entry.summary

                # 清理 HTML
                content_text = self._clean_html(content_text)

                # 摘要
                summary = content_text[:200] + "..." if len(content_text) > 200 else content_text

                # 标签
                tags = [tag.term for tag in getattr(entry, "tags", [])]

                article = Article(
                    title=entry.get("title", "").strip(),
                    content=content_text,
                    url=entry.get("link", ""),
                    author=entry.get("author", ""),
                    published_at=published_at,
                    summary=summary,
                    tags=tags,
                    source=feed_title
                )
                articles.append(article)
            except Exception:
                continue

        return articles

    def _clean_html(self, html: str) -> str:
        """清理 HTML 标签，保留纯文本"""
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            import re
            return re.sub(r'<[^>]+>', '', html).strip()

    def test_connection(self) -> dict[str, Any]:
        """测试 RSS 源连通性"""
        try:
            feed = self._fetch_feed()
            if feed.bozo:
                return {
                    "success": False,
                    "message": f"Feed 异常: {feed.bozo_exception}",
                    "entries_count": 0
                }
            return {
                "success": True,
                "message": f"正常，共 {len(feed.entries)} 篇文章",
                "feed_title": feed.feed.get("title", ""),
                "entries_count": len(feed.entries)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {e}",
                "entries_count": 0
            }


# ========================================================================
# 便捷函数
# ========================================================================

def collect(url: str, **kwargs) -> dict[str, Any]:
    """
    便捷函数：采集单个 RSS

    Args:
        url: RSS URL
        **kwargs: timeout, max_items, proxy

    Returns:
        同 RSSCollector.collect()
    """
    return RSSCollector(url, **kwargs).collect()


if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("用法: python collector.py <RSS_URL>")
        sys.exit(1)

    url = sys.argv[1]
    collector = RSSCollector(url)

    # 测试连通性
    print("测试连接...")
    test_result = collector.test_connection()
    print(json.dumps(test_result, ensure_ascii=False, indent=2))

    # 采集
    print("\n采集文章...")
    result = collector.collect()

    if result["success"]:
        print(f"成功: {result['count']} 篇")
        for i, article in enumerate(result["data"], 1):
            print(f"\n{i}. {article.title}")
            print(f"   URL: {article.url}")
            print(f"   摘要: {article.summary[:100]}...")
    else:
        print(f"失败: {result['error']}")