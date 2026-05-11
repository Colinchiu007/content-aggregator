"""
通用网页数据源

从任意 URL 采集内容
"""

import asyncio
from datetime import datetime
from typing import Any
import uuid

from loguru import logger

import httpx

from content_aggregator.sources.base import BaseSource, SourceConfig, TestResult
from content_aggregator.models import Content


class WebSource(BaseSource):
    """通用网页数据源"""

    def __init__(self, config: SourceConfig, proxy: str | None = None, http_config: dict | None = None):
        super().__init__(config)
        self.proxy = proxy
        self.http_config = http_config or {}

    async def connect(self) -> bool:
        """Web 不需要持久连接"""
        return True

    async def collect(self, filters: dict[str, Any] | None = None) -> dict:
        """采集网页内容"""
        import time
        start_time = time.time()

        urls = self.config.config.get("urls", [])
        single_url = self.config.config.get("url")
        if single_url and not urls:
            urls = [single_url]

        if not urls:
            return {
                "success": False,
                "error": "No URLs configured for Web source",
                "contents": []
            }

        all_contents = []
        errors = []

        for url in urls:
            try:
                content = await self._fetch_page(url)
                if content:
                    all_contents.append(content)
            except Exception as e:
                errors.append(f"Error fetching {url}: {str(e)}")
                logger.error(f"Web fetch error: {e}")

        # 应用过滤
        filtered_contents = self._apply_filters(all_contents, filters)

        duration = time.time() - start_time

        return {
            "success": len(all_contents) > 0,
            "contents": filtered_contents,
            "collected_count": len(all_contents),
            "filtered_count": len(all_contents) - len(filtered_contents),
            "duration": duration,
            "error": "; ".join(errors) if errors else None
        }

    async def _fetch_page(self, url: str) -> Content:
        """获取单个网页"""
        timeout = self.http_config.get("timeout", 30)
        
        async with httpx.AsyncClient(
            timeout=timeout, 
            follow_redirects=True, 
            proxy=self.proxy
        ) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            html = response.text

        # 解析 HTML
        content = self._parse_html(html, url)
        
        return content

    def _parse_html(self, html: str, url: str) -> Content:
        """解析 HTML 内容"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except ImportError:
            logger.warning("BeautifulSoup not installed, using simple parsing")
            return self._parse_html_simple(html, url)

        # 提取标题
        title = ""
        if soup.title:
            title = soup.title.string or ""
        
        # 尝试从 meta 标签获取标题
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"]

        # 提取正文内容
        content_text = ""
        
        # 方法1: 从 article 或 main 标签获取
        for tag in soup.find_all(["article", "main", "div"], class_=lambda x: x and any(t in x.lower() for t in ["content", "article", "post", "body", "entry"])):
            text = tag.get_text(separator="\n", strip=True)
            if len(text) > len(content_text):
                content_text = text

        # 方法2: 获取 body
        if not content_text or len(content_text) < 100:
            if soup.body:
                content_text = soup.body.get_text(separator="\n", strip=True)

        # 清理文本
        content_text = self._clean_text(content_text)

        # 提取作者
        author = ""
        author_tag = soup.find("meta", attrs={"name": "author"})
        if author_tag and author_tag.get("content"):
            author = author_tag["content"]

        # 提取发布日期
        published_at = None
        date_tag = soup.find("meta", property="article:published_time")
        if date_tag and date_tag.get("content"):
            try:
                published_at = datetime.fromisoformat(date_tag["content"].replace("Z", "+00:00"))
            except:
                pass

        # 提取描述
        description = ""
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            description = desc_tag["content"]
        else:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                description = og_desc["content"]

        # 提取标签
        tags = []
        keywords_tag = soup.find("meta", attrs={"name": "keywords"})
        if keywords_tag and keywords_tag.get("content"):
            tags = [t.strip() for t in keywords_tag["content"].split(",")]

        content = Content(
            id=str(uuid.uuid4()),
            source_id=self.config.id,
            source_type="web",
            url=url,
            title=title.strip() if title else url,
            content=content_text,
            summary=self._truncate(description or content_text, 200),
            author=author,
            published_at=published_at,
            metadata={
                "source_url": url,
                "tags": tags,
            },
            raw_data={"url": url},
        )

        return content

    def _parse_html_simple(self, html: str, url: str) -> Content:
        """简单 HTML 解析（无 BeautifulSoup）"""
        import re

        # 提取标题
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1) if title_match else url

        # 简单去除 HTML 标签
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        content_text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

        return Content(
            id=str(uuid.uuid4()),
            source_id=self.config.id,
            source_type="web",
            url=url,
            title=title.strip(),
            content=content_text,
            summary=self._truncate(content_text, 200),
            author="",
            published_at=None,
            metadata={"source_url": url},
            raw_data={"url": url},
        )

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        import re

        # 去除多余空白
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        
        # 去除广告文本
        ad_patterns = [
            r"关注.*?公众号",
            r"扫码.*?关注",
            r"点击.*?查看",
            r"广告.*?投放",
        ]
        for pattern in ad_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        return text.strip()

    def _truncate(self, text: str, length: int) -> str:
        """截断文本"""
        if not text:
            return ""
        if len(text) <= length:
            return text
        return text[:length] + "..."

    def _apply_filters(self, contents: list[Content], filters: dict | None) -> list[Content]:
        """应用过滤条件"""
        if not filters:
            return contents

        result = contents

        # 关键词过滤
        if "keywords" in filters:
            keywords = filters["keywords"]
            result = [c for c in result if any(
                k.lower() in c.title.lower() or k.lower() in c.content.lower() 
                for k in keywords
            )]

        # 最小长度过滤
        if "min_length" in filters:
            min_length = filters["min_length"]
            result = [c for c in result if len(c.content) >= min_length]

        return result

    async def test(self) -> TestResult:
        """测试网页源"""
        urls = self.config.config.get("urls", [])
        single_url = self.config.config.get("url")
        if single_url and not urls:
            urls = [single_url]

        if not urls:
            return TestResult(success=False, message="No URLs configured")

        try:
            timeout = self.http_config.get("timeout", 30)
            
            async with httpx.AsyncClient(
                timeout=timeout, 
                follow_redirects=True, 
                proxy=self.proxy
            ) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
                response = await client.get(urls[0], headers=headers)
                response.raise_for_status()
                html = response.text

            # 检查是否有效 HTML
            if "<html" not in html.lower() and "<!doctype" not in html.lower():
                return TestResult(
                    success=False,
                    message="Response is not HTML",
                    details={"content_type": response.headers.get("content-type", "")}
                )

            # 尝试解析标题
            title = ""
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.string if soup.title else ""
            except:
                import re
                title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
                title = title_match.group(1) if title_match else ""

            return TestResult(
                success=True,
                message=f"Page loaded: {title or 'untitled'}",
                details={
                    "url": urls[0],
                    "title": title,
                    "content_length": len(html),
                }
            )
        except Exception as e:
            return TestResult(success=False, message=f"Failed to fetch: {str(e)}")