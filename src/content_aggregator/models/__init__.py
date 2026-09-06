"""
Models package for Content Aggregator.

Phase 2: Content/Article migrated to content-aggregator-shared.
Imports are re-exported from shared.models for backward compatibility.
"""

# Publish-related models (new)
from .publish import PublishRequest, PublishResult, PublishTask

# Content and Article models - migrated to shared, re-exported here
try:
    from content_aggregator_shared.shared.models import Content, Article
except ImportError:
    from ._models import Content, Article  # fallback for dev without shared installed

__all__ = ["PublishRequest", "PublishResult", "PublishTask", "Content", "Article"]
