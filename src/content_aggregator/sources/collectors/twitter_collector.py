"""
Twitter/X 采集器

支持：
- 用户时间线推文（通过 Twitter API v2 或 Nitter 备选）
- 关键词搜索

注意：
- Twitter API 需要 Bearer Token，无 Token 时跳过并提示
- 国内无法直接访问 twitter.com，代理不可用时会跳过
"""

import logging
from datetime import datetime

from content_aggregator.sources.collectors.base_collector import BaseCollector

logger = logging.getLogger(__name__)


class TwitterCollector(BaseCollector):
    """Twitter/X 推文采集器"""

    SOURCE_NAME = "twitter"
    RATE_LIMIT = 5.0

    def __init__(self, bearer_token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.bearer_token = bearer_token

    async def _fetch(self, username: str | None = None, query: str | None = None,
                     max_results: int = 20, **kwargs) -> list[dict]:
        """
        采集 Twitter 推文

        参数：
            username: Twitter 用户名（不含 @）
            query: 搜索关键词（与 username 二选一）
            max_results: 最大条数
        """
        if not self.bearer_token:
            raise EnvironmentError("TWITTER_BEARER_TOKEN 未配置，请在 config.yaml 中设置 sources.twitter.bearer_token")

        username = username or self.config.get("username")
        query = query or self.config.get("query")

        client = await self._get_client()
        headers = {"Authorization": f"Bearer {self.bearer_token}"}

        if username:
            # 用户时间线
            url = "https://api.twitter.com/2/users/by/username/{}/tweets".format(username)
            params = {
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,public_metrics,lang",
                "expansions": "author_id",
                "user.fields": "name,username",
            }
        elif query:
            # 搜索
            url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                "query": query,
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,public_metrics,lang",
            }
        else:
            raise ValueError("Twitter 采集器需要 username 或 query 参数")

        response = await client.get(url, params=params, headers=headers, proxy=self.proxy)
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise RuntimeError(f"Twitter API 错误: {data['errors']}")

        includes = data.get("includes", {})
        users = {u["id"]: u for u in includes.get("users", [])}
        tweets = data.get("data", [])
        results = []

        for tweet in tweets:
            author = users.get(tweet.get("author_id", {}), {})
            metrics = tweet.get("public_metrics", {})
            created = tweet.get("created_at", "")
            published = None
            if created:
                try:
                    published = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append({
                "title": tweet.get("text", "")[:200] or "",
                "content": tweet.get("text", "") or "",
                "url": f"https://twitter.com/{author.get('username', '')}/status/{tweet.get('id', '')}",
                "author": author.get("name", "") or "",
                "published_at": published,
                "summary": tweet.get("text", "")[:300] or "",
                "tags": [],
                "source": self.SOURCE_NAME,
                "metadata": {
                    "tweet_id": tweet.get("id", ""),
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "lang": tweet.get("lang", ""),
                }
            })

        logger.info(f"[Twitter] 采集到 {len(results)} 条推文")
        return results