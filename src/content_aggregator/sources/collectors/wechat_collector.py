"""
微信公众号采集器

支持：
- 公众号历史文章列表（通过搜狗微信搜索 / 新榜等第三方）
- 关键词搜索文章

注意：
- 公众号需要账号授权或第三方平台，无配置时跳过
- 搜索方式较灵活，新榜/搜狗均可作为来源
"""

import logging
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class WeChatCollector(BaseCollector):
    """微信公众号采集器"""

    SOURCE_NAME = "wechat"
    RATE_LIMIT = 3.0

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key

    async def _fetch(self, biz: str | None = None, name: str | None = None,
                     keyword: str | None = None, max_results: int = 20, **kwargs) -> list[dict]:
        """
        采集微信公众号文章

        参数：
            biz: 公众号 biz 参数（从文章链接中提取，如 biz=MzA3...）
            name: 公众号名称（搜索用）
            keyword: 关键词搜索
            max_results: 最大条数
        """
        if not self.api_key and not name:
            raise EnvironmentError(
                "WECHAT_API_KEY 或公众号名称未配置，请在 config.yaml 中设置 sources.wechat.name 或 sources.wechat.api_key"
            )

        biz = biz or self.config.get("biz")
        name = name or self.config.get("name")
        keyword = keyword or self.config.get("keyword")

        client = await self._get_client()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }

        if biz:
            # 通过 biz 获取历史消息
            url = "https://mp.weixin.qq.com/cgi-bin/appmsg"
            params = {
                "action": "list_ex",
                "begin": 0,
                "count": min(max_results, 20),
                "fakeid": biz,
                "type": 9,
                "token": "",
                "lang": "zh_CN",
                "f": "json",
                "ajax": 1,
            }
            headers["Cookie"] = self.config.get("cookie", "")
        elif name:
            # 通过名称搜索公众号
            if self.api_key:
                # 使用第三方 API（如新榜 API）
                url = "https://api.newrank.cn/api/v1/wechat/search"
                params = {
                    "keyword": name,
                    "size": min(max_results, 20),
                }
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                # 使用搜狗微信搜索（免费，无需 Key）
                url = "https://weixin.sogou.com/weixin"
                params = {
                    "type": 2,
                    "query": name,
                    "ie": "utf8",
                    "s_from": "input",
                    "_": "1678900000000",
                }
        else:
            raise ValueError("微信公众号采集器需要 biz 或 name 参数")

        response = await client.get(url, params=params, headers=headers, proxy=self.proxy)
        response.raise_for_status()

        # 解析响应
        items = self._parse_response(response, keyword=keyword)
        results = []

        for item in items:
            published_str = item.get("datetime", "") or item.get("crawl_time", "")
            published = None
            if published_str:
                try:
                    published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append({
                "title": item.get("title", "") or "",
                "content": item.get("content", item.get("digest", "")),
                "url": item.get("url", "") or item.get("link", "") or "",
                "author": item.get("author", item.get("account_name", "")) or "",
                "published_at": published,
                "summary": item.get("digest", "") or item.get("content", "")[:300],
                "tags": [],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "biz": item.get("biz", ""),
                    "account_name": item.get("account_name", ""),
                }
            })

        logger.info(f"[WeChat] 采集到 {len(results)} 篇公众号文章")
        return results

    def _parse_response(self, response, **kwargs) -> list[dict]:
        """解析响应数据（兼容多种 API 格式）"""
        try:
            data = response.json()
        except Exception:
            # HTML 响应（搜狗）
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.select("div.news-box li")
            results = []
            for article in articles:
                title_el = article.select_one("h3 a, .txt-box h3 a")
                results.append({
                    "title": title_el.get_text(strip=True) if title_el else "",
                    "url": title_el.get("href", "") if title_el else "",
                    "datetime": article.select_one(".s2 span, .s-p, .time").get_text(strip=True) if article else "",
                    "author": article.select_one(".s-p, .account").get_text(strip=True) if article else "",
                })
            return results

        # JSON 响应
        if isinstance(data, dict):
            if "data" in data:
                return data["data"]
            if "items" in data:
                return data["items"]
            if "list" in data:
                return data["list"]
        return []