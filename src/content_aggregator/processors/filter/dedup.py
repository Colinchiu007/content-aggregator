"""
内容去重过滤器（Phase 2 已迁移至 shared 库）

本文件为 re-export shim。
"""

from content_aggregator_shared.shared.processors.dedup import (
    DedupFilter,
    DedupFilterConfig,
)

__all__ = ["DedupFilter", "DedupFilterConfig"]
