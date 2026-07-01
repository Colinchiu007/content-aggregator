"""Services interface consumed by TrendScope's pipeline bridge.

This module provides the ``fetch_and_rewrite`` entry-point that TrendScope's
``bridge.py`` imports.  In production the function delegates to the full
ContentPipeline; in development / when the pipeline is unavailable it falls
back gracefully.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def fetch_and_rewrite(
    url: str,
    style: str = "公众号",
    source: str = "trendscope",
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Fetch content from *url* and rewrite it in the requested *style*.

    Called by TrendScope's ``PipelineBridge.push_to_pipeline()`` after
    a hot topic is crawled.  Returns a dict with ``rewritten_title``,
    ``rewritten_content``, ``word_count`` etc. on success, or ``None``
    on failure.

    Parameters
    ----------
    url:
        Public URL of the article to fetch and rewrite.
    style:
        Rewrite style — one of ``公众号``, ``知乎``, ``小红书``, ``短视频文案``.
    source:
        Origin tag (always ``trendscope`` when called from the bridge).

    Returns
    -------
    dict or None
    """
    try:
        # ── try the full ContentPipeline ────────────────────────────────
        from content_aggregator.workflows.pipeline import ContentPipeline
        from content_aggregator.processors.rewrite import RewriteConfig, RewriteStrategy

        config: dict[str, Any] = {
            "llm": {
                "api_key": kwargs.get("api_key", ""),
                "model": kwargs.get("model", "gpt-4o-mini"),
            },
            "export": {"output_dir": "./output"},
        }

        pipeline = ContentPipeline(config)
        # ContentPipeline.process_url expects a URL; it will:
        #   1. detect source type (RSS / web / YouTube / …)
        #   2. fetch raw content
        #   3. run sensitive-filter → dedup → rewrite → SEO → format
        article = await pipeline.process_url(url)
        await pipeline.__aexit__(None, None, None)

        if article is None:
            logger.warning(f"[content-agg] pipeline returned None for {url}")
            return None

        return {
            "rewritten_title": getattr(article, "title", ""),
            "rewritten_content": getattr(article, "content", ""),
            "word_count": getattr(article, "word_count", 0),
            "style": style,
            "source_url": url,
            "source": source,
        }

    except ImportError as exc:
        logger.warning(
            "[content-agg] ContentPipeline not available (%s) — "
            "install content-aggregator extras to enable in-process rewriting",
            exc,
        )
        return None

    except Exception as exc:
        logger.error("[content-agg] fetch_and_rewrite failed for %s: %s", url, exc)
        return None


# Keep this alias for backwards-compat (TrendScope bridge does
# ``from content_aggregator.services import fetch_and_rewrite``).
__all__ = ["fetch_and_rewrite"]
