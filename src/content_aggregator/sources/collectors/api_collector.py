"""
通用 API 采集器

支持：
- REST API (JSON)
- GraphQL API
- 自定义 JSONPath / XPath 提取

标准化字段：
    title, content, url, author, published_at, summary, tags, source

适用场景：
- 自建 CMS/API
- 第三方内容平台（如 Notion API、Strapi、自定义后端）
- 任何提供标准化 JSON/XML 接口的内容源
"""

import logging
from datetime import datetime
from typing import Any

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class APICollector(BaseCollector):
    """通用 API 采集器"""

    SOURCE_NAME = "api"
    RATE_LIMIT = 2.0

    def __init__(self, api_url: str | None = None, method: str = "GET",
                 headers: dict | None = None, params: dict | None = None,
                 body: dict | None = None, json_path: str | None = None,
                 auth: tuple | None = None, **kwargs):
        """
        参数：
            api_url: API 地址
            method: HTTP 方法（GET/POST）
            headers: 请求头
            params: URL 查询参数
            body: POST 请求体
            json_path: JSONPath 表达式（定位文章列表，如 $.data.articles）
            auth: Basic Auth (username, password) 元组
        """
        super().__init__(**kwargs)
        self.api_url = api_url or self.config.get("api_url")
        self.method = method.upper()
        self.headers = headers or self.config.get("headers", {})
        self.params = params or self.config.get("params", {})
        self.body = body or self.config.get("body", {})
        self.json_path = json_path or self.config.get("json_path", "$.data")
        self.auth = auth or self.config.get("auth")

    async def _fetch(self, api_url: str | None = None, max_results: int = 50, **kwargs) -> list[dict]:
        """
        调用 API 并提取数据

        参数：
            api_url: 覆盖默认 api_url
            max_results: 最大条数
        """
        url = api_url or self.api_url
        if not url:
            raise ValueError("API 采集器需要 api_url 参数")

        client = await self._get_client()
        req_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ContentAggregator/1.0)",
            "Accept": "application/json, application/xml, text/xml, */*",
        }
        req_headers.update(self.headers or {})

        # Basic Auth
        if self.auth:
            import base64
            creds = base64.b64encode(f"{self.auth[0]}:{self.auth[1]}".encode()).decode()
            req_headers["Authorization"] = f"Basic {creds}"

        # 发起请求
        logger.info(f"[API] 请求: {url}")
        if self.method == "POST":
            response = await client.post(url, params=self.params, json=self.body,
                                         headers=req_headers, proxy=self.proxy)
        else:
            response = await client.get(url, params=self.params,
                                         headers=req_headers, proxy=self.proxy)
        response.raise_for_status()

        # 解析响应
        content_type = response.headers.get("content-type", "")
        results = []

        if "json" in content_type:
            results = self._extract_json(response.json())
        elif "xml" in content_type:
            results = self._extract_xml(response.text)
        else:
            # 尝试 JSON
            try:
                results = self._extract_json(response.json())
            except Exception:
                results = self._extract_xml(response.text)

        logger.info(f"[API] 采集到 {len(results)} 条")
        return results[:max_results]

    def _extract_json(self, data: Any) -> list[dict]:
        """使用 jsonpath 提取数据"""
        import jsonpath_ng

        try:
            # 解析 json_path
            expr = jsonpath_ng.parse(self.json_path)
            matches = expr.find(data)
            if matches:
                items = matches[0].value
                if isinstance(items, list):
                    return [self._normalize_item(item) for item in items]
                else:
                    return [self._normalize_item(items)]
        except Exception as e:
            logger.warning(f"[API] JSONPath 提取失败 '{self.json_path}': {e}，尝试 $.data")

        # 回退：直接从 data 中找列表
        if isinstance(data, list):
            return [self._normalize_item(item) for item in data]
        if isinstance(data, dict):
            for key in ["data", "items", "results", "list", "articles", "posts"]:
                if key in data and isinstance(data[key], list):
                    return [self._normalize_item(item) for item in data[key]]

        return []

    def _extract_xml(self, xml_text: str) -> list[dict]:
        """从 XML 中提取数据"""
        import xml.etree.ElementTree as ET

        results = []
        try:
            root = ET.fromstring(xml_text)
            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0].strip("{")

            for item in root.findall(f".//{{{ns}}}item") if ns else root.findall(".//item"):
                d = {}
                for child in item:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    d[tag] = child.text or ""
                results.append(self._normalize_item(d))
        except Exception as e:
            logger.warning(f"[API] XML 解析失败: {e}")

        return results

    def _normalize_item(self, item: dict) -> dict:
        """将任意字典规范化为标准字段"""
        # 常见字段名映射
        field_map = {
            "title": ["title", "name", "subject", "heading"],
            "content": ["content", "body", "text", "description", "summary"],
            "url": ["url", "link", "href", "uri", "path"],
            "author": ["author", "creator", "user", "username", "writer"],
            "published_at": ["published_at", "publish_time", "created_at", "date", "timestamp", "created_time"],
            "summary": ["summary", "excerpt", "intro", "digest"],
            "tags": ["tags", "categories", "labels", "category"],
        }

        normalized = {"source": self.SOURCE_NAME, "metadata": {}}

        for std_field, candidates in field_map.items():
            for candidate in candidates:
                if candidate in item and item[candidate]:
                    value = item[candidate]
                    # 时间字段转换
                    if std_field == "published_at" and isinstance(value, (int, float)):
                        try:
                            value = datetime.fromtimestamp(value)
                        except Exception:
                            value = None
                    normalized[std_field] = value
                    break

        # 保留原始数据的其他字段到 metadata
        for k, v in item.items():
            if k not in normalized:
                normalized["metadata"][k] = v

        # 填充空字段
        normalized.setdefault("title", "")
        normalized.setdefault("content", "")
        normalized.setdefault("url", "")
        normalized.setdefault("author", "")
        normalized.setdefault("published_at", None)
        normalized.setdefault("summary", "")
        normalized.setdefault("tags", [])

        return normalized