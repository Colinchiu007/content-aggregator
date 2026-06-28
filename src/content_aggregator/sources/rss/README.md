# RSS 采集器模块

独立采集 RSS/Atom 源的文章内容。

## 输入

- RSS/Atom URL
- 可选：过滤条件（关键词、日期范围）

## 输出

```json
{
  "success": true,
  "data": [
    {
      "title": "文章标题",
      "content": "文章正文（纯文本）",
      "url": "原文链接",
      "author": "作者",
      "published_at": "2026-05-11T10:00:00",
      "summary": "前200字符摘要",
      "tags": ["标签1", "标签2"]
    }
  ],
  "count": 10,
  "error": null
}
```

## 配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| url | string | 必填 | RSS URL |
| timeout | int | 30 | 超时秒数 |
| max_items | int | 20 | 最大采集数量 |

## 使用方法

```python
from content_aggregator.sources.rss import RSSCollector

collector = RSSCollector(url="https://www.ruanyifeng.com/blog/atom.xml")
result = collector.collect()

if result["success"]:
    for article in result["data"]:
        print(article["title"])
```

## 依赖

- httpx
- feedparser
- bs4（可选，用于 HTML 清理）