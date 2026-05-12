"""
网站地图采集器

支持：
- 标准 XML Sitemap（sitemap.xml）
- Sitemap Index（多个 sitemap 索引）
- 嵌套 Sitemap

通用性：只要目标网站提供了 sitemap.xml，就能自动发现并采集所有链接。
国内网站大多数提供 sitemap，是重要的标准化采集来源。
"""

import logging
import re
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class SitemapCollector(BaseCollector):
    """网站 sitemap 采集器"""

    SOURCE_NAME = "sitemap"
    RATE_LIMIT = 2.0

    # 常见 sitemap 路径
    SITEMAP_PATHS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap.xml.gz",
        "/wp-sitemap.xml",
        "/sitemap-index.xml",
        "/feed/sitemap.xml",
        "/sitemap-news.xml",
    ]

    async def _fetch(self, base_url: str | None = None, include: list[str] | None = None,
                     exclude: list[str] | None = None, max_items: int = 100, **kwargs) -> list[dict]:
        """
        采集网站 sitemap

        参数：
            base_url: 网站根地址（如 https://example.com）
            include: 只采集包含特定路径的 URL（可选）
            exclude: 排除特定路径的 URL（可选）
            max_items: 最大采集条数
        """
        import xml.etree.ElementTree as ET

        base_url = base_url or self.config.get("base_url")
        if not base_url:
            raise ValueError("Sitemap 采集器需要 base_url 参数")

        # 去掉末尾斜杠
        base_url = base_url.rstrip("/")

        client = await self._get_client()
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ContentAggregator/1.0; +https://github.com/Colinchiu007/content-aggregator)",
        }

        all_urls = []

        # 1. 尝试 sitemap index
        index_urls = []
        for path in self.SITEMAP_PATHS:
            if "index" not in path:
                index_urls.append(base_url + path)

        sitemap_xml = None
        for url in index_urls:
            try:
                resp = await client.get(url, headers=headers, proxy=self.proxy, timeout=15)
                if resp.status_code == 200:
                    sitemap_xml = resp.text
                    logger.info(f"[Sitemap] 发现: {url}")
                    break
            except Exception:
                continue

        if not sitemap_xml:
            raise RuntimeError(f"无法找到 sitemap.xml，尝试路径: {', '.join(index_urls)}")

        # 2. 解析
        root = ET.fromstring(sitemap_xml)

        # 检测命名空间
        ns = {}
        if root.tag.startswith("{"):
            ns[""] = root.tag.split("}")[0].strip("{")
        else:
            ns[""] = ""

        sitemap_ns = "" if "" in ns else "sm"

        # 处理 sitemap index
        is_index = root.tag.endswith("sitemapindex") or root.tag.endswith("}sitemapindex")

        if is_index:
            # 收集子 sitemap URL
            child_sitemaps = []
            for sm in root.findall(f".//{{{ns['']}}}sitemap") if ns[''] else root.findall(".//sitemap"):
                loc = sm.find(f"{{{ns['']}}}loc") if ns[''] else sm.find("loc")
                if loc is not None and loc.text:
                    child_sitemaps.append(loc.text)

            logger.info(f"[Sitemap] 发现 {len(child_sitemaps)} 个子 sitemap")

            # 逐个采集（最多 5 个，避免过多请求）
            for child_url in child_sitemaps[:5]:
                try:
                    resp = await client.get(child_url, headers=headers, proxy=self.proxy, timeout=15)
                    child_urls = self._extract_urls(resp.text, ns, include, exclude)
                    all_urls.extend(child_urls)
                except Exception as e:
                    logger.warning(f"[Sitemap] 子 sitemap 采集失败: {child_url} - {e}")
        else:
            # 直接解析 url 列表
            all_urls = self._extract_urls(sitemap_xml, ns, include, exclude)

        # 限制数量
        all_urls = all_urls[:max_items]

        logger.info(f"[Sitemap] 采集到 {len(all_urls)} 个 URL")
        return all_urls

    def _extract_urls(self, xml_text: str, ns: dict, include: list | None, exclude: list | None) -> list[dict]:
        """从 sitemap XML 中提取 URL"""
        import xml.etree.ElementTree as ET

        results = []
        try:
            root = ET.fromstring(xml_text)
            url_ns = "" if "" in ns else "sm"

            for url_el in root.findall(f".//{{{ns['']}}}url") if ns[''] else root.findall(".//url"):
                loc_el = url_el.find(f"{{{ns['']}}}loc") if ns[''] else url_el.find("loc")
                if loc_el is None:
                    continue

                url = loc_el.text or ""
                if not url:
                    continue

                # 过滤
                if include and not any(p in url for p in include):
                    continue
                if exclude and any(p in url for p in exclude):
                    continue

                # 取最后修改时间
                lastmod = url_el.find(f"{{{ns['']}}}lastmod") if ns[''] else url_el.find("lastmod")
                lastmod_str = lastmod.text if lastmod is not None else None
                published = None
                if lastmod_str:
                    try:
                        published = datetime.fromisoformat(lastmod_str.split("T")[0])
                    except Exception:
                        pass

                results.append({
                    "title": "",
                    "content": "",
                    "url": url,
                    "author": "",
                    "published_at": published,
                    "summary": "",
                    "tags": [],
                    "source": self.SOURCE_NAME,
                    "metadata": {"lastmod": lastmod_str}
                })
        except ET.ParseError as e:
            logger.warning(f"[Sitemap] XML 解析失败: {e}")

        return results