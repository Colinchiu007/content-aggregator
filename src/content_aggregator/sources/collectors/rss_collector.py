"""
RSS 采集器

支持标准 RSS/Atom 格式输入，自动检测格式。

标准化字段：
    title, content, url, author, published_at, summary, tags, source

当 RSS 条目正文过短时（< min_body_length 字符），
自动访问文章 URL 抓取完整正文，并按域名限速避免封禁。
"""

import asyncio
import feedparser
import logging
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """RSS/Atom 采集器"""

    SOURCE_NAME = "rss"
    RATE_LIMIT = 1.0   # RSS 请求间隔可以短一些

    # 正文抓取配置（子类可覆盖，None 表示关闭自动抓取）
    min_body_length: int = 200        # 正文 < 此字符数时才抓取完整文章
    article_rate_limit: float = 2.0    # 同一域名最小请求间隔（秒）

    def __init__(self, *args, min_body_length: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if min_body_length is not None:
            self.min_body_length = min_body_length
        # 每个域名的最后请求时间（用于速率限制）
        self._domain_last_request: dict[str, float] = {}
        # 每个域名的 asyncio.Lock（防止同一域名并发请求）
        self._domain_locks: dict[str, asyncio.Lock] = {}

    async def _fetch(self, url: str | None = None, max_items: int = 20, **kwargs) -> list[dict]:
        """
        采集 RSS 源

        参数：
            url: RSS 链接（优先）或从 self.config 获取
            max_items: 最大采集条数
            min_body_length: 可选，覆盖实例级最小正文长度阈值
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

        response = await client.get(target_url, headers=headers)
        response.raise_for_status()

        # 解析
        feed = feedparser.parse(response.text)

        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS 解析失败：{feed.bozo_exception}")

        # 确认是否启用正文抓取
        threshold = kwargs.get("min_body_length", self.min_body_length)
        fetch_article_body = threshold is not None and threshold > 0

        results = []
        for entry in feed.entries[:max_items]:
            article = self._parse_entry(entry, feed.feed)

            # 正文过短时，尝试抓取完整文章
            if fetch_article_body:
                raw_content = article["content"].strip()
                if len(raw_content) < threshold:
                    article_url = article.get("url") or ""
                    if article_url:
                        full_body = await self._fetch_article_body(article_url)
                        if full_body:
                            article["content"] = full_body
                            logger.info(
                                f"[RSS] 已抓取完整正文: {article['title'][:40]}... "
                                f"({len(raw_content)} → {len(full_body)} chars)"
                            )

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
            "source": self.config.get("name") or self.SOURCE_NAME,
            "metadata": {
                "feed_title": getattr(feed, "title", "") or "",
                "feed_url": getattr(feed, "link", "") or "",
            }
        }

    # ------------------------------------------------------------------
    # 正文抓取（带域名级速率限制）
    # ------------------------------------------------------------------

    async def _fetch_article_body(self, url: str) -> str | None:
        """
        抓取文章页面的完整正文（带域名级速率限制）。

        速率限制策略：
        - 同一域名两次请求至少间隔 article_rate_limit 秒
        - 同一域名的并发请求会被合并（后续请求等待前一个完成）
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if not domain:
                return None

            # 获取或创建该域名的锁（防止同一域名并发请求）
            if domain not in self._domain_locks:
                self._domain_locks[domain] = asyncio.Lock()
            lock = self._domain_locks[domain]

            async with lock:
                # 速率限制：检查距上次请求的时间
                last = self._domain_last_request.get(domain, 0)
                elapsed = time.monotonic() - last
                if elapsed < self.article_rate_limit:
                    await asyncio.sleep(self.article_rate_limit - elapsed)
                self._domain_last_request[domain] = time.monotonic()

                # 下载页面
                client = await self._get_client()
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
                try:
                    response = await client.get(url, headers=headers, timeout=15.0)
                    response.raise_for_status()
                except Exception as e:
                    logger.warning(f"[RSS] 抓取正文失败 {url}: {e}")
                    return None

                # 编码处理
                html = response.text
                encoding = self._detect_encoding(response, html)
                if encoding:
                    try:
                        html = response.content.decode(encoding)
                    except Exception:
                        pass

                return self._extract_article_body(html, url)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[RSS] 抓取正文异常 {url}: {e}")
            return None

    def _detect_encoding(self, response, html: str) -> str | None:
        """从响应头和 HTML 中检测编码"""
        # 优先从 Content-Type 头获取
        content_type = response.headers.get("content-type", "")
        if "charset=" in content_type.lower():
            m = re.search(r"charset=([^;\s]+)", content_type, re.I)
            if m:
                return m.group(1).strip()
        # 其次从 HTML <meta> 标签获取
        m = re.search(r'<meta[^>]+charset=["\s]*([\w-]+)', html, re.I)
        if m:
            return m.group(1).strip()
        return None

    def _extract_article_body(self, html: str, base_url: str) -> str | None:
        """
        从 HTML 中提取文章正文。

        策略（按优先级）：
        1. <article> 标签
        2. <main> 标签
        3. [role=main] 属性
        4. class/id 含 article/post/content/entry 的 div
        5. 最大的 <div> 块（启发式）
        6. <body> 兜底
        """
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        # 移除干扰元素
        for tag in soup.find_all(
            ["script", "style", "nav", "footer", "header", "aside",
             "noscript", "iframe", "form", "button", "svg"]
        ):
            tag.decompose()

        # 按策略依次查找
        selectors = [
            lambda s: s.find("article"),
            lambda s: s.find("main"),
            lambda s: s.find(attrs={"role": "main"}),
            lambda s: s.find("div", class_=re.compile(r"\barticle\b", re.I)),
            lambda s: s.find("div", id=re.compile(r"\barticle\b", re.I)),
            lambda s: s.find("div", class_=re.compile(r"\bpost\b", re.I)),
            lambda s: s.find("div", id=re.compile(r"\bpost\b", re.I)),
            lambda s: s.find("div", class_=re.compile(r"\b(content|entry)\b", re.I)),
            lambda s: s.find("div", class_=re.compile(r"\btext\b", re.I)),
        ]

        for selector in selectors:
            element = selector(soup)
            if element and self._element_has_substantial_text(element):
                text = self._clean_article_text(element)
                if len(text) >= 100:
                    return text

        # 启发式：找最大文本块
        candidates = []
        for div in soup.find_all("div"):
            text = div.get_text(separator="\n", strip=True)
            if len(text) >= 200:
                candidates.append((len(text), text))

        if candidates:
            candidates.sort(reverse=True)
            best = candidates[0][1]
            # 去掉开头可能是导航/侧边栏的短文本段落
            lines = best.split("\n")
            while lines and len(lines[0].strip()) < 20:
                lines.pop(0)
            return "\n".join(lines).strip()

        # 兜底：body
        body = soup.find("body")
        if body:
            return self._clean_article_text(body)

        return None

    def _element_has_substantial_text(self, element) -> bool:
        """判断元素是否包含足够多的有效文本"""
        text = element.get_text(strip=True)
        return len(text) >= 150

    def _clean_article_text(self, element) -> str:
        """清理元素文本：去空行、去导航残留"""
        lines = []
        for line in element.get_text(separator="\n", strip=True).split("\n"):
            line = line.strip()
            # 跳过过短的行（可能是菜单）
            if len(line) < 10:
                continue
            # 跳过导航/页脚类关键词
            skip_patterns = [
                "cookie", "privacy policy", "terms of", "subscribe to",
                "sign up", "newsletter", "登录", "注册", "copyright",
                "京ICP备", "All rights reserved", "更多精彩内容",
                "更多内容", "相关推荐", "热门文章", "猜你喜欢",
            ]
            if any(p.lower() in line.lower() for p in skip_patterns):
                continue
            lines.append(line)
        # 合并连续空行
        result = []
        prev_empty = False
        for line in lines:
            if line:
                result.append(line)
                prev_empty = False
            elif not prev_empty:
                result.append("")
                prev_empty = True
        return "\n".join(result).strip()

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _strip_html(self, html: str) -> str:
        """去除 HTML 标签（保留纯文本）"""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)
