"""
敏感词过滤器（Phase 2 已迁移至 shared 库）

本文件为 re-export shim。
"""

from content_aggregator_shared.shared.processors.sensitive import (
    SensitiveFilter,
    SensitiveFilterConfig,
)

__all__ = ["SensitiveFilter", "SensitiveFilterConfig"]
