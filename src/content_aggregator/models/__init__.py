"""
Models package for Content Aggregator.
"""

# Publish-related models (new)
from .publish import PublishRequest, PublishResult, PublishTask

# Content and Article models (existing - re-export for backward compatibility)
try:
    # Try to import from models.py (at package level)
    from ..models import Content
except ImportError:
    # If not found, define a dummy class
    class Content:
        pass

try:
    # Try to import Article from collectors
    from ..sources.collectors.collector import Article
except ImportError:
    # If not found, define a dummy class
    class Article:
        pass

__all__ = ["PublishRequest", "PublishResult", "PublishTask", "Content", "Article"]
