"""数据源模块"""

from content_aggregator.sources.base import BaseSource, SourceConfig, TestResult
from content_aggregator.sources.rss import RSSCollector

__all__ = ["BaseSource", "SourceConfig", "TestResult", "RSSCollector"]