"""翻译器 re-export shim — Phase 2 Step 4 已迁移至 shared 库"""

from content_aggregator_shared.shared.rewriters.translator import (
    TranslatorProcessor,
    TranslationConfig,
    TranslationLanguage,
    TranslationResult,
)

__all__ = [
    "TranslatorProcessor",
    "TranslationConfig",
    "TranslationLanguage",
    "TranslationResult",
]
