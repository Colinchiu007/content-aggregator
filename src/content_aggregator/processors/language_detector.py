"""
语言检测模块（Phase 2 已迁移至 shared 库）

本文件为 re-export shim，保持 content-aggregator 旧代码零感知。
"""

from content_aggregator_shared.shared.processors.language_detector import (
    CJK_RANGES,
    KANA_RANGES,
    HANGUL_RANGES,
    LANGUAGE_NAMES,
    LANGUAGE_DETECTION_PROMPT,
    LanguageDetectResult,
    LanguageDetector,
    get_language_name,
)

__all__ = [
    "CJK_RANGES",
    "KANA_RANGES",
    "HANGUL_RANGES",
    "LANGUAGE_NAMES",
    "LANGUAGE_DETECTION_PROMPT",
    "LanguageDetectResult",
    "LanguageDetector",
    "get_language_name",
]
