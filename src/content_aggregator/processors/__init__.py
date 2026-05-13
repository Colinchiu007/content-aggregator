"""处理器模块"""
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy, RewriteResult
from content_aggregator.processors.formatter import ContentFormatter, markdown_to_html_inline, markdown_to_wechat_html
from content_aggregator.processors.translator import TranslatorProcessor, TranslationConfig, TranslationLanguage, TranslationResult
from content_aggregator.processors.seo import SEOProcessor, SEOConfig, SEOResult

__all__ = [
    # 改写
    "RewriteProcessor", "RewriteConfig", "RewriteStrategy", "RewriteResult",
    # 格式化
    "ContentFormatter", "markdown_to_html_inline", "markdown_to_wechat_html",
    # 翻译
    "TranslatorProcessor", "TranslationConfig", "TranslationLanguage", "TranslationResult",
    # SEO
    "SEOProcessor", "SEOConfig", "SEOResult",
]