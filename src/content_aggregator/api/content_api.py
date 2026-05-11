"""
内容聚合 API
提供 Skill 封装的标准化接口
"""

import json
import asyncio
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.exporters import Exporter, to_markdown, to_html, to_json, to_txt, to_xiaohongshu


class ContentAPI:
    """
    内容聚合 API

    提供标准化的 Skill 接口，供其他模块调用

    使用示例：
        api = ContentAPI(config)
        
        # 处理 RSS
        articles = await api.collect_rss(url)
        
        # 改写内容
        articles = await api.rewrite_contents(articles)
        
        # 导出
        paths = await api.export_articles(articles, formats=["markdown", "html"])
        
        # 或者一键处理
        paths = await api.process_and_export(url)
    """

    def __init__(self, config: dict[str, Any]):
        """
        初始化 API

        参数：
            config: 配置字典，包含 llm、export 等配置
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.export_config = config.get("export", {})
        self.output_dir = self.export_config.get("output_dir", "./output/exports")

        self._pipeline: ContentPipeline | None = None
        self._exporter: Exporter | None = None

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self._pipeline = ContentPipeline(self.config)
        await self._pipeline.__aenter__()
        self._exporter = Exporter(self.output_dir)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self._pipeline:
            await self._pipeline.__aexit__(exc_type, exc_val, exc_tb)

    # ========================================================================
    # 采集接口
    # ========================================================================

    async def collect_rss(self, url: str) -> list[dict]:
        """
        采集 RSS 内容

        参数：
            url: RSS URL

        返回：
            内容字典列表
        """
        from content_aggregator.sources.rss import RSSSource, SourceConfig

        source_config = SourceConfig(
            id=str(uuid.uuid4()),
            name="rss_collector",
            source_type="rss",
            config={"url": url}
        )
        source = RSSSource(source_config)
        result = await source.collect()

        if result.get("success"):
            return [c.to_dict() if hasattr(c, 'to_dict') else {
                "id": c.id,
                "title": c.title,
                "content": c.content,
                "url": c.url,
            } for c in result.get("contents", [])]
        return []

    # ========================================================================
    # 改写接口
    # ========================================================================

    async def rewrite_article(self, article: dict, strategy: str = "REWRITE") -> dict:
        """
        改写单篇文章

        参数：
            article: 文章字典，包含 id、title、content
            strategy: 改写策略

        返回：
            改写后的文章字典
        """
        from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
        from content_aggregator.models import Content

        # 创建 Content 对象
        content = Content(
            id=article.get("id", str(uuid.uuid4())),
            source_id="api",
            source_type="custom",
            url=article.get("url", ""),
            title=article.get("title", ""),
            content=article.get("content", ""),
            summary=article.get("summary", ""),
        )

        # 配置改写
        rewrite_config = RewriteConfig(
            strategy=RewriteStrategy[strategy.upper()],
            min_word_count=500,
            max_word_count=5000,
            target_word_count=3000
        )

        # 执行改写
        async with RewriteProcessor(self.config) as processor:
            result = await processor.rewrite(content, rewrite_config)

            if result.success:
                return {
                    "success": True,
                    "id": article.get("id"),
                    "title": result.title or article.get("title"),
                    "content": result.rewritten_content,
                    "summary": result.summary,
                    "metadata": result.metadata
                }
            else:
                return {
                    "success": False,
                    "error": result.error
                }

    # ========================================================================
    # 导出接口
    # ========================================================================

    async def export_article(self, article: dict, formats: list[str] = None) -> list[str]:
        """
        导出文章到文件

        参数：
            article: 文章字典
            formats: 格式列表（markdown/html/json/txt/xiaohongshu）

        返回：
            文件路径列表
        """
        if formats is None:
            formats = ["markdown"]

        from content_aggregator.models import Article

        # 转换为 Article 对象
        art = Article(
            id=article.get("id", str(uuid.uuid4())),
            title=article.get("title", "Untitled"),
            original_title=article.get("original_title", ""),
            source=article.get("source", ""),
            source_url=article.get("url", ""),
            content=article.get("content", ""),
            summary=article.get("summary", ""),
            tags=article.get("tags", []),
            metadata=article.get("metadata", {})
        )

        exporter = Exporter(self.output_dir)
        paths = []
        for fmt in formats:
            try:
                path = exporter.export(art, fmt)
                paths.append(path)
            except Exception as e:
                logger.error(f"Export failed ({fmt}): {e}")

        return paths

    # ========================================================================
    # 一键处理接口
    # ========================================================================

    async def process_and_export(self, url: str, formats: list[str] = None) -> dict:
        """
        一键处理：采集 → 改写 → 导出

        参数：
            url: RSS URL
            formats: 导出格式列表

        返回：
            结果字典，包含 paths（文件路径列表）和 article（文章内容）
        """
        if formats is None:
            formats = ["markdown"]

        async with ContentPipeline(self.config) as pipeline:
            # 处理
            article = await pipeline.process_url(url, rewrite=True)
            if not article:
                return {"success": False, "error": "No content collected"}

            # 导出
            paths = []
            for fmt in formats:
                try:
                    path = pipeline.exporter.export(article, fmt)
                    paths.append(path)
                except Exception as e:
                    logger.error(f"Export failed ({fmt}): {e}")

            return {
                "success": True,
                "article": article.to_dict(),
                "paths": paths
            }


# ========================================================================
# 便捷函数
# ========================================================================

async def quick_process(url: str, config: dict) -> dict:
    """
    快速处理 RSS URL

    参数：
        url: RSS URL
        config: 配置字典

    返回：
        结果字典
    """
    async with ContentAPI(config) as api:
        return await api.process_and_export(url, ["markdown", "html"])


def export_to_format(article: dict, format_type: str) -> str:
    """
    将文章导出为指定格式

    参数：
        article: 文章字典
        format_type: 格式类型

    返回：
        格式化后的字符串
    """
    from content_aggregator.models import Article

    art = Article(
        id=article.get("id", str(uuid.uuid4())),
        title=article.get("title", "Untitled"),
        content=article.get("content", ""),
    )

    if format_type in ("markdown", "md"):
        return to_markdown(art)
    elif format_type in ("html", "wechat"):
        return to_html(art)
    elif format_type == "json":
        return to_json(art)
    elif format_type == "txt":
        return to_txt(art)
    elif format_type in ("xiaohongshu", "xhs"):
        return to_xiaohongshu(art)
    else:
        return to_markdown(art)