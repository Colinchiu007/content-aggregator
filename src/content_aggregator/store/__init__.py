"""
数据存储模块 — 从 MediaCrawler StoreFactory 模式适配

提供统一的采集数据持久化接口。

使用:
    # JSON 存储
    store = JsonDataStore("./output/collected")
    result = await collector.collect()
    store.save(result)

    # 数据库存储
    store = DbDataStore("./output/collected.db")
    await store.save(result)

    # 通过工厂创建
    store = create_data_store("json", base_dir="./output/collected")
"""

from .abstract import DataStore
from .json_store import JsonDataStore
from .db_store import DbDataStore
from .excel_store import ExcelDataStore, EXCEL_AVAILABLE

__all__ = [
    "DataStore",
    "JsonDataStore",
    "DbDataStore",
    "ExcelDataStore",
    "EXCEL_AVAILABLE",
]


def create_data_store(store_type: str = "json", **kwargs) -> DataStore:
    """
    数据存储工厂

    Args:
        store_type: 存储类型 ("json" / "db" / "excel")
        **kwargs: 传递给存储实现的参数

    Returns:
        DataStore 实例
    """
    if store_type == "json":
        return JsonDataStore(**kwargs)
    if store_type == "db":
        return DbDataStore(**kwargs)
    if store_type == "excel":
        return ExcelDataStore(**kwargs)

    raise ValueError(f"不支持的存储类型: {store_type!r}。支持: json, db, excel")
