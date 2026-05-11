"""
RSS 采集器模块

使用示例:
    from content_aggregator.sources.rss import RSSCollector

    collector = RSSCollector("https://www.ruanyifeng.com/blog/atom.xml")
    result = collector.collect()

    if result["success"]:
        for article in result["data"]:
            print(article.title, article.url)
"""

from .collector import RSSCollector, Article, CollectorConfig, collect

__all__ = ["RSSCollector", "Article", "CollectorConfig", "collect"]