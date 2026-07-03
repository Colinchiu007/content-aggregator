"""Content Aggregator — thin SDK facade for TrendScope bridge and orchestrator.

Re-exports key capabilities from the src/ tree so that
external consumers (TrendScope bridge, platform-orchestrator) can import
from a stable package namespace.

Usage::

    from content_aggregator.services import fetch_and_rewrite
    result = await fetch_and_rewrite(url="https://...", style="公众号")

    from content_aggregator import ContentAPI
    async with ContentAPI(config) as api:
        result = await api.process_and_export(url)
"""

from content_aggregator.api.content_api import ContentAPI
from content_aggregator.workflows.pipeline import ContentPipeline

__all__ = ["ContentAPI", "ContentPipeline", "fetch_and_rewrite"]
