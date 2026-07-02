"""
Content Aggregator - 内容聚合与改写平台
=====================================

通用内容处理中台，将互联网热文转化为标准化内容资产，供多平台发布使用。

主要功能：
- 内容采集（RSS、自定义URL等）
- AI改写（DeepSeek/OpenAI/Qwen）
- 多格式导出（Markdown、HTML、JSON、TXT）
- Skill封装，供其他模块调用

使用示例：
    from content_aggregator import ContentPipeline

    pipeline = ContentPipeline(config)
    article = await pipeline.process_url("https://example.com/rss.xml")
"""

__version__ = "0.1.0"

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.api.content_api import ContentAPI

__all__ = ["ContentPipeline", "ContentAPI"]
