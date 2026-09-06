"""Re-export shim: Last30DaysCollector 已迁移至 shared 库"""

from content_aggregator_shared.shared.collectors.last30days_collector import (
    Last30DaysCollector,
    DEFAULT_SOURCES,
    ENGAGEMENT_NORMALIZERS,
    SOURCE_FETCHERS,
    normalize_engagement,
    compute_freshness_score,
    rrf_score,
    create_last30days_collector,
)

__all__ = [
    "Last30DaysCollector",
    "DEFAULT_SOURCES",
    "ENGAGEMENT_NORMALIZERS",
    "SOURCE_FETCHERS",
    "normalize_engagement",
    "compute_freshness_score",
    "rrf_score",
    "create_last30days_collector",
]
