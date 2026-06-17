"""
网站地图采集器

支持：
- 标准 XML Sitemap（/sitemap.xml）
- Sitemap Index（包含多个 sitemap 的索引）
- 递归 Sitemap

通过法：只要目标网站提供 sitemap.xml，就能自动递归采集所有链接。
注意事项：网站未提供 sitemap 时需要改用其他采集源。
"""

import logging
import re
from datetime import datetime
from xml.etree import ElementTree as ET

from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult

logger = logging.getLogger(__name__)


class SitemapCollector(BaseCollector):
    """网站 sitemap 采集器"""

    SOURCE_NAME = "sitemap"
    RATE_LIMIT = 2.0

    SITEMAP_PATHS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap.xml.gz",
        "/wp-sitemap.xml",
        "/sitemap-index.xml",
        "/feed/sitemap.xml",
        "/sitemap-news.xml",
    ]

    async def _fetch(self, base_url=None, include=None, exclude=None, max_items=100, **kwargs):
        base_url = base_url or self.config.get("base_url")
        if not base_url:
            raise ValueError("Sitemap 采集器需要 base_url 参数")

        base_url = base_url.rstrip("/")
        client = await self._get_client()
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ContentAggregator/1.0)"}

        all_urls = []

        # Try sitemap at common paths
        sitemap_found = False
        for path_suffix in self.SITEMAP_PATHS:
            url = base_url + path_suffix
            try:
                resp = await client.get(url, headers=headers, timeout=15)
                if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                    sitemap_xml = resp.text
                    logger.info(f"[Sitemap] Found: {url}")
                    sitemap_found = True
                    break
            except Exception:
                continue

        if not sitemap_found:
            raise RuntimeError(f"无法找到 sitemap.xml，已尝试路径: {', '.join(self.SITEMAP_PATHS)}")

        root = ET.fromstring(sitemap_xml)
        ns = {}
        if root.tag.startswith("{"):
            ns[""] = root.tag.split("}")[0].strip("{")
        else:
            ns[""] = ""

        is_index = root.tag.endswith("sitemapindex") or "sitemapindex" in root.tag

        if is_index:
            child_sitemaps = []
            tag_sitemap = "{{{0}}}sitemap".format(ns[""]) if ns[""] else "sitemap"
            tag_loc = "{{{0}}}loc".format(ns[""]) if ns[""] else "loc"
            for sm in root.findall(".//" + tag_sitemap):
                loc = sm.find(tag_loc)
                if loc is not None and loc.text:
                    child_sitemaps.append(loc.text)

            logger.info(f"[Sitemap] Found {len(child_sitemaps)} child sitemaps")
            for child_url in child_sitemaps[:5]:
                try:
                    resp = await client.get(child_url, headers=headers, timeout=15)
                    child_urls = self._extract_urls(resp.text, ns, include, exclude)
                    all_urls.extend(child_urls)
                except Exception as e:
                    logger.warning(f"[Sitemap] Child sitemap failed: {child_url} - {e}")
        else:
            all_urls = self._extract_urls(sitemap_xml, ns, include, exclude)

        all_urls = all_urls[:max_items]
        logger.info(f"[Sitemap] Collected {len(all_urls)} URLs")
        return all_urls

    def _extract_urls(self, xml_text, ns, include, exclude):
        results = []
        try:
            root = ET.fromstring(xml_text)
            tag_url = "{{{0}}}url".format(ns[""]) if ns[""] else "url"
            tag_loc = "{{{0}}}loc".format(ns[""]) if ns[""] else "loc"
            tag_lastmod = "{{{0}}}lastmod".format(ns[""]) if ns[""] else "lastmod"

            for url_el in root.findall(".//" + tag_url):
                loc_el = url_el.find(tag_loc)
                if loc_el is None or not loc_el.text:
                    continue
                url = loc_el.text

                if include and not any(p in url for p in include):
                    continue
                if exclude and any(p in url for p in exclude):
                    continue

                lastmod_el = url_el.find(tag_lastmod)
                lastmod_str = lastmod_el.text if lastmod_el is not None else None
                published = None
                if lastmod_str:
                    try:
                        published = datetime.fromisoformat(lastmod_str.split("T")[0])
                    except Exception:
                        pass

                results.append({
                    "url": url,
                    "published_at": published,
                    "metadata": {"lastmod": lastmod_str},
                })
        except ET.ParseError as e:
            logger.warning(f"[Sitemap] XML parse failed: {e}")
        return results

    async def collect(self, **kwargs):
        """采集 sitemap 中的页面内容"""
        from content_aggregator.sources.collectors.base_collector import SourceResult

        base_url = kwargs.get("base_url") or self.config.get("base_url", "")
        max_items = kwargs.get("max_items", 100)

        if not base_url:
            return SourceResult(success=False, data=[], error="base_url is required", source_name="sitemap", collected_count=0)

        try:
            url_dicts = await self._fetch(base_url=base_url, max_items=max_items)
        except Exception as e:
            return SourceResult(success=False, data=[], error=str(e), source_name="sitemap", collected_count=0)

        if not url_dicts:
            return SourceResult(success=True, data=[], error=None, source_name="sitemap", collected_count=0)

        contents = []
        client = await self._get_client()
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ContentAggregator/1.0)"}

        for item in url_dicts[:max_items]:
            url = item.get("url", "")
            if not url:
                continue
            try:
                resp = await client.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    continue
                html = resp.text

                t = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                title = t.group(1).strip() if t else ""

                clean = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.IGNORECASE | re.DOTALL)
                paras = re.findall(r"<p[^>]*>(.*?)</p>", clean, re.IGNORECASE | re.DOTALL)
                clean_paras = []
                for p in paras:
                    text = re.sub(r"<[^>]+>", "", p).strip()
                    if text and len(text) > 20:
                        clean_paras.append(text)
                body = "\n\n".join(clean_paras[:10])

                if not body:
                    text_only = re.sub(r"<[^>]+>", " ", clean)
                    text_only = re.sub(r"\s+", " ", text_only).strip()
                    body = text_only[:2000]

                contents.append({
                    "title": title,
                    "content": body,
                    "url": url,
                    "source": "Sitemap - " + base_url,
                    "word_count": len(body),
                })
            except Exception as e:
                logger.warning(f"[Sitemap] Failed {url}: {e}")
                continue

        return SourceResult(success=True, data=contents, error=None, source_name="sitemap", collected_count=len(contents))
