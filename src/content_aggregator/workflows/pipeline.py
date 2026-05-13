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
from content_aggregator.sources.rss import RSSCollector
from content_aggregator.sources.base import BaseSource, SourceConfig
from content_aggregator.sources import get_collector
from content_aggregator.sources.collectors.base_collector import BaseCollector, SourceResult
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
from content_aggregator.processors.formatter import ContentFormatter
from content_aggregator.processors.translator import TranslatorProcessor, TranslationConfig, TranslationLanguage
from content_aggregator.processors.seo import SEOProcessor, SEOConfig
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
                - http: HTTP配置（包含proxy）
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.export_config = config.get("export", {})
        self.http_config = config.get("http", {})
        self.output_dir = self.export_config.get("output_dir", "./output/exports")
        self.proxy = self.http_config.get("proxy")

        self.sources_config = config.get("sources", {})
        self.translation_config = config.get("translation", {})

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

    async def process_url(self, url: str, rewrite: bool = True, rewrite_config: RewriteConfig | None = None, seo: bool = False) -> Article | None:
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

        # 创建RSS源（传入代理配置）
        source_config = SourceConfig(
            id=str(uuid.uuid4()),
            name="custom_rss",
            source_type="rss",
            config={"url": url}
        )
        source = RSSCollector(url=url, name="custom_rss", proxy=self.proxy)

        # 采集
        result = await source.collect_async()
        if not result.get("success") or not result.get("data"):
            logger.error(f"No content collected from {url}")
            return None

        # 取第一篇
        content = result["data"][0]
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

                # SEO 优化
                if seo:
                    try:
                        async with SEOProcessor(self.config) as seo_proc:
                            seo_result = await seo_proc.optimize(content)
                            if seo_result.success:
                                article.tags = seo_result.optimized_tags
                                article.metadata["seo_keywords"] = seo_result.keywords
                                article.metadata["seo_description"] = seo_result.meta_description
                                article.metadata["seo_title"] = seo_result.meta_title
                    except Exception as e:
                        logger.warning(f"SEO failed: {e}")

                return article
            else:
                logger.error(f"Rewrite failed: {rewrite_result.error}")
                # 改写失败，返回原始内容
                return Article.from_content(content)

        # 不改写，直接构建 Article
        return Article(
            id=content.id if hasattr(content, 'id') and content.id else str(uuid.uuid4()),
            title=content.title,
            content=content.content,
            source=content.source_id if hasattr(content, 'source_id') else getattr(content, 'name', '') or '',
            source_url=content.url if hasattr(content, 'url') else '',
            published_at=getattr(content, 'published_at', None),
            author=getattr(content, 'author', None) or getattr(content, 'name', None) or '',
        )

    async def process_all_sources(
        self,
        rewrite: bool = True,
        translate: bool = False,
        target_language: str | None = None,
        seo: bool = False,
        formats: list[str] | None = None,
        limit_per_source: int = 20,
    ) -> dict[str, Any]:
        """
        批量采集 config.yaml 中所有已启用的数据源

        支持的源类型（全部从 config.yaml sources 读取）：
            rss, youtube, twitter, tiktok, douyin, xiaohongshu, wechat, sitemap, api

        网络错误时自动跳过，不中断流程。

        参数：
            rewrite: 是否改写
            translate: 是否翻译
            target_language: 目标语言（如 EN / JA）
            formats: 导出格式列表
            limit_per_source: 每个源最大采集数

        返回：
            {
                "articles": [...],        # 成功处理的 Article 列表
                "source_results": [...],   # 每个源的采集结果
                "summary": {               # 汇总
                    "total_sources": 10,
                    "success": 7,
                    "skipped": 3,
                    "total_articles": 25,
                }
            }
        """
        import time
        start = time.time()
        all_articles: list[Article] = []
        source_results: list[dict] = []
        total_skipped = 0

        # 初始化翻译器（如果需要）
        translator = None
        translation_lang = None
        if translate and self.translation_config.get("enabled", False):
            lang_code = target_language or self.translation_config.get("default_language", "EN")
            try:
                translation_lang = TranslationLanguage(lang_code)
            except ValueError:
                logger.warning(f"不支持的翻译语言: {lang_code}，跳过翻译")
                translate = False
            else:
                translator = TranslatorProcessor(self.config)

        # SEO processor (lazy init)
        seo_processor = None
        if seo:
            seo_processor = SEOProcessor(self.config)
            await seo_processor.__aenter__()

        # 各源配置映射
        source_configs_map = {
            "rss": self._parse_rss_sources,
            "youtube": self._parse_single_config,
            "twitter": self._parse_single_config,
            "tiktok": self._parse_single_config,
            "douyin": self._parse_single_config,
            "xiaohongshu": self._parse_single_config,
            "wechat": self._parse_single_config,
            "sitemap": self._parse_single_config,
            "api": self._parse_single_config,
        }

        for source_type, parse_fn in source_configs_map.items():
            entries = parse_fn(source_type)
            if not entries:
                continue

            for entry in entries:
                entry_name = entry.get("name", source_type)
                logger.info(f"[Pipeline] 采集源: {entry_name} ({source_type})")

                try:
                    collector = get_collector(
                        source_type,
                        config=entry,
                        proxy=self.proxy,
                        timeout=self.http_config.get("timeout", 30),
                    )
                    result: SourceResult = await collector.collect(**entry)

                    source_results.append({
                        "source_name": entry_name,
                        "source_type": source_type,
                        "success": result.success,
                        "collected": result.collected_count,
                        "skipped": result.skipped_count,
                        "error": result.error,
                        "duration": result.duration,
                    })

                    if not result.success:
                        total_skipped += 1
                        if result.error:
                            print(f"  [SKIP] {entry_name}: {result.error}")
                        continue

                    # 转换为 Article
                    for item_data in result.data:
                        article = Article(
                            id=str(uuid.uuid4()),
                            title=item_data.get("title", ""),
                            content=item_data.get("content", ""),
                            source=item_data.get("source", source_type),
                            source_url=item_data.get("url", ""),
                            author=item_data.get("author", ""),
                            published_at=item_data.get("published_at"),
                            summary=item_data.get("summary", ""),
                            word_count=len(item_data.get("content", "")),
                        )

                        # 改写
                        if rewrite and self.rewrite_processor and article.word_count > 0:
                            try:
                                content = Content(
                                    id=article.id,
                                    title=article.title,
                                    content=article.content,
                                    source_type=article.source,
                                    url=article.source_url,
                                    author=article.author,
                                )
                                rewrite_result = await self.rewrite_processor.rewrite(content)
                                if rewrite_result.success:
                                    article.content = rewrite_result.rewritten_content
                                    article.word_count = len(rewrite_result.rewritten_content)
                                    article.title = rewrite_result.title or article.title
                            except Exception as e:
                                logger.warning(f"改写失败（{article.title}）: {e}")

                        # 翻译
                        if translate and translator and translation_lang and article.word_count > 0:
                            try:
                                content = Content(
                                    id=article.id,
                                    title=article.title,
                                    content=article.content,
                                    source_type=article.source,
                                    url=article.source_url,
                                )
                                trans_config = TranslationConfig(
                                    target_language=translation_lang,
                                    tone=self.translation_config.get("tone", "casual"),
                                )
                                trans_result = await translator.translate(content, trans_config)
                                if trans_result.success:
                                    article.original_title = article.title
                                    article.title = f"{article.title} ({translation_lang.value})"
                                    article.content = trans_result.translated_content
                                    article.word_count = len(trans_result.translated_content)
                            except Exception as e:
                                logger.warning(f"翻译失败（{article.title}）: {e}")

                        # SEO 优化
                        if seo and seo_processor and article.word_count > 0:
                            try:
                                seo_content = Content(
                                    id=article.id,
                                    title=article.title,
                                    content=article.content,
                                    source_type=article.source,
                                    url=article.source_url,
                                )
                                seo_result = await seo_processor.optimize(seo_content)
                                if seo_result.success:
                                    article.tags = seo_result.optimized_tags
                                    article.metadata["seo_keywords"] = seo_result.keywords
                                    article.metadata["seo_description"] = seo_result.meta_description
                                    article.metadata["seo_title"] = seo_result.meta_title
                            except Exception as e:
                                logger.warning(f"SEO failed ({article.title}): {e}")

                        all_articles.append(article)

                        # 导出
                        if formats:
                            for fmt in formats:
                                try:
                                    self.exporter.export(article, fmt)
                                except Exception as e:
                                    logger.error(f"导出失败 ({fmt}): {e}")

                    print(f"  [OK] {entry_name}: 采集 {result.collected_count} 篇")

                except Exception as e:
                    total_skipped += 1
                    error_msg = f"[{entry_name}] 初始化/采集异常: {e}"
                    logger.warning(error_msg)
                    print(f"  [SKIP] {error_msg}")
                    source_results.append({
                        "source_name": entry_name,
                        "source_type": source_type,
                        "success": False,
                        "collected": 0,
                        "skipped": 1,
                        "error": error_msg,
                        "duration": 0,
                    })

        elapsed = time.time() - start
        success_sources = sum(1 for r in source_results if r["success"])

        # Cleanup SEO processor
        if seo_processor:
            await seo_processor.__aexit__(None, None, None)

        print(f"\n{'=' * 60}")
        print(f"汇总")
        print(f"{'=' * 60}")
        print(f"  数据源总数: {len(source_results)}")
        print(f"  成功: {success_sources}")
        print(f"  跳过: {total_skipped}")
        print(f"  文章总数: {len(all_articles)}")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"{'=' * 60}")

        return {
            "articles": all_articles,
            "source_results": source_results,
            "summary": {
                "total_sources": len(source_results),
                "success": success_sources,
                "skipped": total_skipped,
                "total_articles": len(all_articles),
                "elapsed": elapsed,
            }
        }

    def _parse_rss_sources(self, source_type: str) -> list[dict]:
        """解析 RSS 源配置"""
        sources = self.sources_config.get("rss", [])
        entries = []
        for src in sources:
            if not src.get("enabled", True):
                continue
            entries.append({"name": src.get("name", "rss"), "url": src.get("url"), "max_items": 20})
        return entries

    def _parse_single_config(self, source_type: str) -> list[dict]:
        """解析单配置数据源（youtube/twitter/douyin 等）"""
        source_cfg = self.sources_config.get(source_type, {})

        # 优先从 channels/users/accounts/sites/endpoints 读取
        for list_key in ["channels", "users", "accounts", "sites", "endpoints"]:
            items = source_cfg.get(list_key, [])
            if items:
                entries = []
                for item in items:
                    if not item.get("enabled", True):
                        continue
                    entry = dict(source_cfg)  # 复制全局配置（api_key/cookie 等）
                    entry.update(item)  # 用单项配置覆盖
                    entry["name"] = item.get("name", source_type)
                    entry["max_items"] = item.get("max_items", 20)
                    entries.append(entry)
                return entries

        # 如果有 api_url 或 base_url 等直接字段，视为单个源
        if source_cfg.get("api_url") or source_cfg.get("base_url"):
            return [{**source_cfg, "name": source_cfg.get("name", source_type), "max_items": 20}]

        return []

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