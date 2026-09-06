"""Re-export shim: 基类已迁移到 content_aggregator_shared.shared.collectors"""

from content_aggregator_shared.shared.collectors.base import BaseCollector, SourceResult

__all__ = ["BaseCollector", "SourceResult"]
