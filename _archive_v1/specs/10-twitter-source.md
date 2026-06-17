# Twitter 数据源详细规格

> 版本: 1.0.0  
> 最后更新: 2026-05-27  
> 状态: 基于 `collectors/twitter_collector.py` 反向工程

---

## 1. 概述

### 1.1 功能定位

Twitter Collector 通过 **Twitter API v2** 采集推文数据，支持两种模式：
- **用户时间线模式**：采集指定用户的最新推文
- **关键词搜索模式**：搜索包含特定关键词的近期推文

**核心能力**:
- 采集用户最新推文
- 关键词搜索推文
- 获取推文公开指标（点赞数、转推数等）
- 支持中英文推文采集

### 1.2 数据流转

```
Twitter API v2 → _fetch() → 推文元数据 → SourceResult
```

---

## 2. 配置规格

### 2.1 config.yaml 配置

```yaml
# config.yaml
sources:
  twitter:
    bearer_token: "AAAAAAAA..."     # Twitter API Bearer Token（必需）
    username: "elonmusk"          # 默认用户名（可选，二选一）
    query: "AI agent"              # 默认搜索关键词（可选，二选一）
    max_results: 20                # 最大采集数量
```

### 2.2 环境变量

| 变量名 | 说明 | 优先级 |
|--------|------|----------|
| `TWITTER_BEARER_TOKEN` | Twitter API Bearer Token | 低于 config.yaml |
| `TWITTER_USERNAME` | 默认用户名 | 低于 kwargs |
| `TWITTER_QUERY` | 默认搜索关键词 | 低于 kwargs |

### 2.3 Bearer Token 获取

1. 访问 https://developer.twitter.com/en/portal/dashboard
2. 创建 App（需要审核）
3. 在 "Keys and tokens" 中生成 Bearer Token
4. 复制到 `config.yaml` 的 `sources.twitter.bearer_token`

---

## 3. 采集模式

### 3.1 用户时间线模式

**触发条件**: 提供 `username`，不提供 `query`

**API 端点**: `GET https://api.twitter.com/2/users/by/username/{username}/tweets`

**参数**:
```python
params = {
    "max_results": min(max_results, 100),
    "tweet.fields": "created_at,public_metrics,lang",
    "expansions": "author_id",
    "user.fields": "name,username",
}
```

**返回字段**:
- `data[].id` → `tweet_id`
- `data[].text` → `title` 和 `content`
- `data[].created_at` → `published_at`
- `data[].public_metrics.like_count` → `metadata.likes`
- `data[].public_metrics.retweet_count` → `metadata.retweets`
- `includes.users[].name` → `author`
- `includes.users[].username` → URL 中的用户名

### 3.2 关键词搜索模式

**触发条件**: 提供 `query`

**API 端点**: `GET https://api.twitter.com/2/tweets/search/recent`

**参数**:
```python
params = {
    "query": query,
    "max_results": min(max_results, 100),
    "tweet.fields": "created_at,public_metrics,lang",
    "expansions": "author_id",
    "user.fields": "name,username",
}
```

**搜索语法**:
| 操作符 | 说明 | 示例 |
|--------|------|------|
| `keyword` | 包含关键词 | `AI agent` |
| `"exact phrase"` | 精确匹配短语 | `"large language model"` |
| `#hashtag` | 包含话题标签 | `#AI` |
| `from:username` | 来自特定用户 | `from:elonmusk` |
| `retweets_of:username` | 转推特定用户的推文 | `retweets_of:openai` |
| `-keyword` | 排除关键词 | `AI -GPT` |

---

## 4. 数据模型

### 4.1 输出格式（SourceResult.data[]）

```python
{
    "title": "推文前 200 字符",
    "content": "推文全文",
    "url": "https://twitter.com/username/status/tweet_id",
    "author": "用户显示名称",
    "published_at": datetime(2026, 5, 27, 22, 0, 0),
    "summary": "推文前 300 字符",
    "tags": [],
    "source": "twitter",
    "metadata": {
        "tweet_id": "1234567890",
        "likes": 1500,
        "retweets": 300,
        "lang": "en",
    }
}
```

### 4.2 metadata 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `tweet_id` | str | 推文 ID（19 位数字） |
| `likes` | int | 点赞数 |
| `retweets` | int | 转推数 |
| `lang` | str | 推文语言代码（en/zh/ja 等） |

---

## 5. 错误处理

### 5.1 常见错误

| 错误类型 | 原因 | 处理方式 |
|----------|------|----------|
| `EnvironmentError` | `bearer_token` 未配置 | 抛出例外，由 Pipeline 捕获 |
| `HTTPStatusError(401)` | Bearer Token 无效 | 抛出 RuntimeError |
| `HTTPStatusError(403)` | 权限不足（App 未审核） | 抛出 RuntimeError |
| `HTTPStatusError(429)` | 请求频率超限 | 抛出 RuntimeError，建议增加 `RATE_LIMIT` |
| `HTTPStatusError(500+)` | Twitter 服务器错误 | 抛出 RuntimeError，优雅跳过 |

### 5.2 错误处理实现

```python
# twitter_collector.py 中的错误处理
try:
    response = await client.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
except HTTPStatusError as e:
    if e.response.status_code == 401:
        raise RuntimeError(f"Twitter API 认证失败：Bearer Token 无效")
    elif e.response.status_code == 403:
        raise RuntimeError(f"Twitter API 权限不足：App 可能未审核")
    elif e.response.status_code == 429:
        raise RuntimeError(f"Twitter API 请求频率超限：请稍后重试")
    else:
        raise RuntimeError(f"Twitter API 错误：{e.response.status_code}")
except Exception as e:
    logger.error(f"[Twitter] 采集失败: {e}")
    return []
```

---

## 6. 限流控制

### 6.1 默认限流

```python
class TwitterCollector(BaseCollector):
    RATE_LIMIT = 5.0  # 请求间隔 5 秒
```

**理由**:
- Twitter API v2 免费层级限制：
  - 用户时间线：每 15 分钟 900 次请求
  - 关键词搜索：每 15 分钟 180 次请求
- 实际应限制频率，避免触发 429 错误

### 6.2 配额管理

**查看配额**: https://developer.twitter.com/en/portal/products/free

**优化建议**:
- 使用用户时间线模式（配额更宽松）
- 缓存用户 ID（避免重复查询）
- 使用 `max_results` 限制返回数量

---

## 7. 使用示例

### 7.1 基本用法

```python
from content_aggregator.sources.collectors.twitter_collector import TwitterCollector

# 1. 创建 Collector
collector = TwitterCollector(
    bearer_token="AAAAAAAA...",
)

# 2. 采集用户时间线
import asyncio

async def main():
    result = await collector.collect(
        username="elonmusk",
        max_results=10,
    )
    
    if result.success:
        print(f"采集到 {result.collected_count} 条推文")
        for item in result.data:
            print(f"- {item['title']}")
    else:
        print(f"采集失败: {result.error}")

asyncio.run(main())
```

### 7.2 搜索推文

```python
result = await collector.collect(
    query="AI agent tutorial -GPT",  # 搜索包含 "AI agent tutorial" 但不包含 "GPT"
    max_results=20,
)
```

### 7.3 使用 config.yaml 配置

```python
# config.yaml
sources:
  twitter:
    bearer_token: "AAAAAAAA..."
    username: "elonmusk"
    max_results: 10

# 代码中
from content_aggregator.sources import get_collector

collector = get_collector("twitter", config=config["sources"]["twitter"])
result = await collector.collect()  # 使用默认 username
```

---

## 8. 测试清单

- [ ] `bearer_token` 未配置 → 抛出 `EnvironmentError`
- [ ] 用户时间线采集返回正确数量推文
- [ ] 关键词搜索采集返回相关推文
- [ ] API 401 错误 → 抛出 RuntimeError
- [ ] API 403 错误 → 抛出 RuntimeError
- [ ] API 429 错误 → 抛出 RuntimeError
- [ ] 限流生效（请求间隔 ≥ 5 秒）
- [ ] 推文元数据正确解析（点赞数、转推数等）
- [ ] URL 正确生成（`https://twitter.com/username/status/tweet_id`）

---

## 9. 下一步行动

1. **补充单元测试** - 测试各种错误场景和降级逻辑
2. **支持更多字段** - 采集推文回复、引用推文等
3. **支持用户关注列表** - 采集关注用户的时间线
4. **优化搜索** - 支持更复杂的搜索语法

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | 初始版本，基于 `twitter_collector.py` 反向工程 |
