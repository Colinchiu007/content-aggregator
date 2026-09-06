"""改写器 re-export shim — Phase 2 Step 4 已迁移至 shared 库"""

from content_aggregator_shared.shared.rewriters.rewriter import (
    RewriteProcessor,
    RewriteConfig,
    RewriteStrategy,
    RewriteResult,
)

__all__ = ["RewriteProcessor", "RewriteConfig", "RewriteStrategy", "RewriteResult"]
