"""
网易新闻采集器 - 基于 AIMedia 原始实现

使用网易 JSONP 接口（去掉 callback 包装即是 JSON）
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

import httpx
from lxml import etree

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult
from content_aggregator.anti_block import AntiBlockManager, create_default_manager

logger = logging.getLogger(__name__)

# 网易频道 JSONP 接口（去掉 callback 参数可获取纯 JSON）
CHANNEL_URLS = {
    "news": "https://news.163.com/special/cm_yaowen20200213/",      # 要闻
    "world": "https://news.163.com/special/cm_war/",                # 国际
    "guonei": "https://news.163.com/special/cm_guonei/",           # 国内
    "tech": "https://tech.163.com/special/00097UHL/tech_datalist.js",  # 科技
    "ent": "https://ent.163.com/special/000381Q1/newsdata_movieidx.js", # 娱乐
    "finance": "https://money.163.com/special/00259K2L/data_stock_redian.js", # 财经
    "edu": "https://edu.163.com/special/002987KB/newsdata_edu_hot.js",      # 教育
    "baby": "https://baby.163.com/special/003687OS/newsdata_hot.js",        # 母婴
}

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Referer": "https://news.163.com/",
}


class WangYiCollector(BaseCollector):
    """网易新闻采集器（基于 AIMedia 原始实现）"""

    SOURCE_NAME = "wangyi"
    RATE_LIMIT = 2.0

    def __init__(
        self,
        name: str = "wangyi",
        config: dict | None = None,
        proxy: str | None = None,
        timeout: int = 30,
        enable_anti_block: bool = False,
        **kwargs,
    ):
        super().__init__(proxy=proxy, timeout=timeout, config=config, **kwargs)
        self.name = name
        self.limit = self.config.get("limit", 20)
        self.enable_anti_block = enable_anti_block
        self.anti_block_manager: AntiBlockManager | None = None

        if enable_anti_block:
            self.anti_block_manager = create_default_manager(enable_proxy=proxy is not None)
            logger.info("[网易新闻] 防封采集机制已启用")

    async def _fetch(self, **kwargs) -> list[dict]:
        """采集网易新闻"""
        import time
        start = time.time()

        channels = self.config.get("channels", ["news"])
        results = []

        for channel in channels:
            if not self.config.get("enabled", True):
                continue

            url = CHANNEL_URLS.get(channel)
            if not url:
                logger.warning(f"[网易新闻] 未知频道: {channel}")
                continue

            try:
                articles = await self._fetch_channel(url, channel)
                results.extend(articles)
                logger.info(f"[网易新闻] {channel} 采集到 {len(articles)} 篇")
            except Exception as e:
                logger.warning(f"[网易新闻] {channel} 采集失败: {e}")

        # 去重
        seen_urls: set[str] = set()
        deduped: list[dict] = []
        for article in results:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped.append(article)

        if self.limit > 0:
            deduped = deduped[: self.limit]

        # 如果配置了 fetch_full_content，则获取每篇文章的完整正文
        if self.config.get("fetch_full_content", True):
            logger.info(f"[网易新闻] 开始获取 {len(deduped)} 篇文章的完整正文...")
            for article in deduped:
                try:
                    detail = await self._fetch_article_detail(article["url"])
                    if detail and detail.get("content"):
                        article["content"] = detail["content"]
                        logger.info(f"[网易新闻] 已获取正文: {article['title'][:30]}... ({len(detail['content'])} 字符)")
                except Exception as e:
                    logger.warning(f"[网易新闻] 获取正文失败 {article['url']}: {e}")

        logger.info(f"[网易新闻] 总计采集 {len(deduped)} 篇（去重后）")
        return deduped

    async def _fetch_channel(self, url: str, channel: str) -> list[dict]:
        """通过 JSONP 接口采集频道新闻列表"""
        client = await self._get_client()
        await self._rate_limit_wait()

        # 网易 JSONP 接口，加 callback 参数
        params = {"callback": "data_callback"}
        response = await client.get(url, params=params, headers=HEADERS)
        response.raise_for_status()
        text = response.text

        # 去掉 JSONP 包装：data_callback(...) 
        if text.startswith("data_callback("):
            text = text[len("data_callback("):]
            # 去掉末尾的 );
            if text.rstrip().endswith(");"):
                text = text.rstrip()[:-2].rstrip()
            elif text.rstrip().endswith(")"):
                text = text.rstrip()[:-1]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"[网易新闻] JSON 解析失败，原始内容: {text[:200]}")
            return []

        articles = []
        # data 是列表，每个元素是新闻 dict
        if isinstance(data, list):
            items = data[:self.limit if self.limit > 0 else None]
        elif isinstance(data, dict) and "data" in data:
            items = data["data"][:self.limit if self.limit > 0 else None]
        else:
            items = []

        for item in items:
            title = item.get("title", "")
            article_url = item.get("docurl", item.get("url", ""))
            if not title or not article_url:
                continue
            # 过滤视频
            if "video" in article_url:
                continue

            # 时间
            published_at = None
            time_str = item.get("time", "")
            if time_str:
                try:
                    # 格式：05/28/2026 14:32:10
                    published_at = datetime.strptime(time_str, "%m/%d/%Y %H:%M:%S")
                except (ValueError, TypeError):
                    pass

            articles.append({
                "title": title,
                "content": item.get("summary", title),  # 先用摘要，fetch_full_content 会替换
                "url": article_url,
                "source": self.SOURCE_NAME,
                "channel": channel,
                "published_at": published_at,
                "metadata": {
                    "imgurl": item.get("imgurl", ""),
                    "docid": item.get("docid", ""),
                },
            })

        return articles

    async def _fetch_article_detail(self, url: str) -> dict | None:
        """获取单篇文章详情（用 lxml 解析）"""
        client = await self._get_client()
        await self._rate_limit_wait()

        try:
            response = await client.get(url, headers=HEADERS)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            logger.warning(f"[网易新闻] 获取详情页失败 {url}: {e}")
            return None

        return self._parse_detail_html(html, url)

    def _parse_detail_html(self, html: str, url: str) -> dict | None:
        """解析详情页 HTML，提取完整文章（使用 BeautifulSoup，避免 lxml 编码问题）"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.warning(f"[网易新闻] BeautifulSoup 解析失败: {e}")
            return None

        # 提取标题
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            return None

        # 提取正文 — 网易文章正文在 #content 或 .post_text 内
        content_parts = []
        content_div = soup.select_one("#content") or soup.select_one(".post_text")
        if content_div:
            # 取所有 p 标签
            for p in content_div.find_all("p"):
                text = p.get_text(strip=True)
                # 过滤太短的行和无效内容
                if len(text) > 10 and "分享" not in text and "微信" not in text:
                    content_parts.append(text)
        else:
            # fallback：直接找所有 p 标签，按长度过滤
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 30:  # 正文段落一般较长
                    content_parts.append(text)

        content = "\n".join(content_parts)

        # 提取发布时间
        date_str = ""
        try:
            # 网易页面有时间 meta 标签
            meta_time = soup.select_one("meta[property='article:published_time']")
            if meta_time:
                date_str = meta_time.get("content", "")
            else:
                # 从 HTML 中搜索日期格式
                match = re.search(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", html)
                if match:
                    date_str = match.group()
        except Exception:
            pass

        # 提取图片列表
        img_list = []
        content_div = soup.select_one("#content") or soup.select_one(".post_text")
        if content_div:
            for img in content_div.find_all("img"):
                src = img.get("src", "")
                if src:
                    img_list.append(src)

        logger.info(f"[网易新闻] 正文解析完成: {title[:30]}... ({len(content)} 字符, {len(img_list)} 张图)")
        return {
            "title": title,
            "content": content,
            "url": url,
            "source": self.SOURCE_NAME,
            "date_str": date_str,
            "img_list": img_list,
        }

    async def _get_client(self):
        """获取 httpx 客户端（复用，强信任环境变量，仅显式传参指定 proxy）"""
        if not hasattr(self, "_client") or self._client is None:
            proxy = self.proxy or self.config.get("proxy")
            self._client = httpx.AsyncClient(
                proxy=proxy,
                timeout=self.timeout,
                follow_redirects=True,
                trust_env=False,
            )
        return self._client

    async def _rate_limit_wait(self):
        """限速等待"""
        import time
        now = time.time()
        if hasattr(self, "_last_request_time"):
            elapsed = now - self._last_request_time
            if elapsed < self.RATE_LIMIT:
                await asyncio.sleep(self.RATE_LIMIT - elapsed)
        self._last_request_time = time.time()

    async def close(self):
        """关闭客户端"""
        if hasattr(self, "_client") and self._client:
            await self._client.aclose()
            self._client = None

