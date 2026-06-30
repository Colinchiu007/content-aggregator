"""
数据存储抽象基类 — 从 MediaCrawler StoreFactory 模式适配

提供统一的数据持久化接口，支持多种后端：
- JSON: 按平台/日期分目录存储为 JSON 文件
- SQLite: 基于 peewee 或 aiosqlite 的数据库存储

使用:
    store = JsonDataStore("./output/collected")
    result = await collector.collect(keyword="AI")
    store.save(result)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from content_aggregator.sources.collectors.base_collector import SourceResult


class DataStore(ABC):
    """数据存储抽象基类"""

    @abstractmethod
    async def save(self, result: SourceResult) -> str:
        """
        保存采集结果

        Args:
            result: 采集结果

        Returns:
            存储路径或标识符
        """
        raise NotImplementedError

    @abstractmethod
    async def query(self, source_name: Optional[str] = None,
                    limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        查询已保存的数据

        Args:
            source_name: 按来源筛选
            limit: 限制条数
            offset: 偏移

        Returns:
            数据列表
        """
        raise NotImplementedError

    @abstractmethod
    async def count(self, source_name: Optional[str] = None) -> int:
        """统计数据条数"""
        raise NotImplementedError
