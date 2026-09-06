"""
LLM 响应处理工具集（Phase 2 已迁移至 shared 库）

本文件为 re-export shim，保持 content-aggregator 旧代码零感知。
"""

from content_aggregator_shared.shared.processors.llm_utils import (
    strip_reasoning_thoughts,
    strip_code_fences,
    extract_json_from_text,
    get_chat_message_text,
    extract_chat_message_json,
    clean_input_content,
    build_thinking_disabled_body,
    looks_like_youtube_bot_challenge,
    looks_like_format_selection_error,
    summarize_yt_error,
)

__all__ = [
    "strip_reasoning_thoughts",
    "strip_code_fences",
    "extract_json_from_text",
    "get_chat_message_text",
    "extract_chat_message_json",
    "clean_input_content",
    "build_thinking_disabled_body",
    "looks_like_youtube_bot_challenge",
    "looks_like_format_selection_error",
    "summarize_yt_error",
]
