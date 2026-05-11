"""
内容处理流水线

使用示例：
    pipeline = ContentPipeline(config)
    
    # 处理单个URL
    article = await pipeline.process_url("https://example.com/rss.xml")
    
    # 处理内容列表
    articles = await pipeline.process_contents(contents)
    
    # 导出
    from content_aggregator.exporters import Exporter
    exporter = Exporter("./output")
    path = exporter.export(article, "markdown")
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from content_aggregator.models import Content, Article
from content_aggregator.sources.rss import RSSSource, SourceConfig
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
from content_aggregator.processors.formatter import ContentFormatter
from content_aggregator.exporters import Exporter


class ContentPipeline:
    """
    内容处理流水线

    流程：RSS采集 → 内容改写 → 格式化 → 导出

    使用示例：
        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-xxx",
                "model": "deepseek-chat"
            },
            "export": {
                "output_dir": "./output/exports"
            }
        }
        
        pipeline = ContentPipeline(config)
        article = await pipeline.process_url("https://example.com/rss.xml")
    """

    def __init__(self, config: dict[str, Any]):
        """
        初始化流水线

        参数：
            config: 配置字典
                - llm: LLM配置
                - sources: 数据源配置
                - export: 导出配置
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.export_config = config.get("export", {})
        self.output_dir = self.export_config.get("output_dir", "./output/exports")

        # 初始化组件
        self.rewrite_processor: RewriteProcessor | None = None
        self.exporter = Exporter(self.output_dir)

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.rewrite_processor = RewriteProcessor(self.config)
        await self.rewrite_processor.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.rewrite_processor:
            await self.rewrite_processor.__aexit__(exc_type, exc_val, exc_tb)

    async def process_url(self, url: str, rewrite: bool = True, rewrite_config: RewriteConfig | None = None) -> Article | None:
        """
        处理单个RSS URL

        参数：
            url: RSS URL
            rewrite: 是否进行改写
            rewrite_config: 改写配置

        返回：
            Article 对象或 None
        """
        logger.info(f"Processing URL: {url}")

        # 创建RSS源
        source_config = SourceConfig(
            id=str(uuid.uuid4()),
            name="custom_rss",
            source_type="rss",
            config={"url": url}
        )
        source = RSSSource(source_config)

        # 采集
        result = await source.collect()
        if not result.get("success") or not result.get("contents"):
            logger.error(f"No content collected from {url}")
            return None

        # 取第一篇
        content = result["contents"][0]
        logger.info(f"Collected: {content.title}")

        # 改写
        if rewrite and self.rewrite_processor:
            rewrite_config = rewrite_config or RewriteConfig(
                strategy=RewriteStrategy.REWRITE,
                min_word_count=500,
                max_word_count=5000,
                target_word_count=3000
            )
            rewrite_result = await self.rewrite_processor.rewrite(content, rewrite_config)

            if rewrite_result.success:
                # 构建 Article
                article = Article(
                    id=rewrite_result.original_content.id if rewrite_result.original_content else str(uuid.uuid4()),
                    title=rewrite_result.title or content.title,
                    original_title=content.title,
                    source=content.source_id,
                    source_url=content.url,
                    author=rewrite_result.original_content.author if rewrite_result.original_content else "",
                    published_at=content.published_at,
                    content=rewrite_result.rewritten_content,
                    summary=rewrite_result.summary,
                    word_count=len(rewrite_result.rewritten_content),
                    metadata=rewrite_result.metadata
                )
                return article
            else:
                logger.error(f"Rewrite failed: {rewrite_result.error}")
                # 改写失败，返回原始内容
                return Article.from_content(content)

        # 不改写，直接返回
        return Article.from_content(content)

    async def process_contents(self, contents: list[Content], rewrite: bool = True) -> list[Article]:
        """
        处理内容列表

        参数：
            contents: Content 对象列表
            rewrite: 是否进行改写

        返回：
            Article 对象列表
        """
        articles = []

        for content in contents:
            # 改写
            if rewrite and self.rewrite_processor:
                rewrite_result = await self.rewrite_processor.rewrite(content)
                if rewrite_result.success:
                    article = Article(
                        id=rewrite_result.original_content.id if rewrite_result.original_content else str(uuid.uuid4()),
                        title=rewrite_result.title or content.title,
                        original_title=content.title,
                        source=content.source_id,
                        source_url=content.url,
                        author=rewrite_result.original_content.author if rewrite_result.original_content else "",
                        published_at=content.published_at,
                        content=rewrite_result.rewritten_content,
                        summary=rewrite_result.summary,
                        word_count=len(rewrite_result.rewritten_content),
                        metadata=rewrite_result.metadata
                    )
                    articles.append(article)
            else:
                article = Article.from_content(content)
                articles.append(article)

        return articles

    async def process_and_export(
        self,
        url: str,
        format_types: list[str] = None,
        rewrite: bool = True
    ) -> list[str]:
        """
        处理并导出

        参数：
            url: RSS URL
            format_types: 导出格式列表
            rewrite: 是否改写

        返回：
            导出文件路径列表
        """
        if format_types is None:
            format_types = ["markdown", "html", "json"]

        article = await self.process_url(url, rewrite)
        if not article:
            return []

        paths = []
        for fmt in format_types:
            try:
                path = self.exporter.export(article, fmt)
                paths.append(path)
            except Exception as e:
                logger.error(f"Export failed ({fmt}): {e}")

        return paths

    def get_article(self, content: str, title: str = "", rewrite: bool = True) -> Article:
        """
        从文本内容创建 Article

        参数：
            content: 文章内容（文本或Markdown）
            title: 文章标题
            rewrite: 是否改写（注：需要 async 调用 rewrite 方法）

        返回：
            Article 对象

        注意：
            此方法同步返回，如果需要改写请使用 process_url
        """
        return Article(
            id=str(uuid.uuid4()),
            title=title or "Untitled",
            content=content,
            word_count=len(content),
        )


# ========================================================================
# 便捷函数
# ========================================================================

async def process_rss(url: str, config: dict, format_types: list[str] = None) -> list[str]:
    """
    便捷函数：处理RSS并导出

    参数：
        url: RSS URL
        config: 配置字典
        format_types: 导出格式列表

    返回：
        导出文件路径列表
    """
    async with ContentPipeline(config) as pipeline:
        return await pipeline.process_and_export(url, format_types)


def quick_export(content: str, title: str, output_dir: str, format_type: str = "markdown") -> str:
    """
    便捷函数：快速导出文本内容

    参数：
        content: 文章内容
        title: 文章标题
        output_dir: 输出目录
        format_type: 格式类型

    返回：
        文件路径
    """
    article = Article(
        id=str(uuid.uuid4()),
        title=title,
        content=content,
        word_count=len(content),
    )
    exporter = Exporter(output_dir)
    return exporter.export(article, format_type)