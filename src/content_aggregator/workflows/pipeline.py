"""
内容处理流水线

使用示例：
    pipeline = ContentPipeline(config)
    
    # 处理单个URL
    article = await pipeline.process_url("https://example.com/rss.xml")
    
    # 处理内容列表
    articles = await pipeline.process_contents(contents, progress_callback=my_callback)
    
    # 导出
    from content_aggregator.exporters import Exporter
    exporter = Exporter("./output")
    path = exporter.export(article, "markdown")
"""

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

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
from content_aggregator.processors.filter.sensitive import SensitiveFilter, SensitiveFilterConfig
from content_aggregator.processors.filter.dedup import DedupFilter, DedupFilterConfig
from content_aggregator.exporters import Exporter
from content_aggregator.notifications import create_notifiers, NotificationMessage


class ContentPipeline:
    """
    内容处理流水线

    流程：RSS采集 → 敏感词过滤 → 去重过滤 → 内容改写 → SEO优化 → 格式化 → 导出

    使用示例：
        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-xxx",
                "model": "deepseek-chat"
            },
            "export": {
                "output_dir": "./output/exports"
            },
            "filter": {
                "sensitive": {"enabled": true},
                "dedup": {"enabled": true}
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
                - filter: 过滤配置（可选）
                - translation: 翻译配置（可选）
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.export_config = config.get("export", {})
        self.http_config = config.get("http", {})
        self.output_dir = self.export_config.get("output_dir", "./output/exports")
        self.proxy = self.http_config.get("proxy")

        self.sources_config = config.get("sources", {})
        self.translation_config = config.get("translation", {})
        self.filter_config = config.get("filter", {})

        # 初始化组件
        self.rewrite_processor: RewriteProcessor | None = None
        self.exporter = Exporter(self.output_dir)
        
        # 初始化过滤器
        self._init_filters()

        # 初始化通知器
        self._init_notifiers()

    def _init_filters(self):
        """初始化过滤器"""
        # 敏感词过滤器
        sensitive_config_dict = self.filter_config.get("sensitive", {})
        sensitive_enabled = sensitive_config_dict.get("enabled", True)
        sensitive_words = sensitive_config_dict.get("words", [
            "色情", "赌博", "毒品", "暴力", "恐怖",
            "诈骗", "传销", "非法集资",
            "加微信", "扫码", "免费领", "点击就送"
        ])
        sensitive_replace_char = sensitive_config_dict.get("replace_char", "*")
        sensitive_strict_mode = sensitive_config_dict.get("strict_mode", False)
        
        sensitive_config = SensitiveFilterConfig(
            enabled=sensitive_enabled,
            words=sensitive_words,
            replace_char=sensitive_replace_char,
            strict_mode=sensitive_strict_mode
        )
        self.sensitive_filter = SensitiveFilter(sensitive_config)
        
        # 去重过滤器
        dedup_config_dict = self.filter_config.get("dedup", {})
        dedup_enabled = dedup_config_dict.get("enabled", True)
        dedup_threshold = dedup_config_dict.get("similarity_threshold", 0.8)
        dedup_exact = dedup_config_dict.get("exact_dedup", True)
        dedup_fuzzy = dedup_config_dict.get("fuzzy_dedup", True)
        dedup_min_length = dedup_config_dict.get("min_length", 50)
        
        # 计算 cache_file 路径（相对于项目根目录的 data/dedup_cache.json）
        import os
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        cache_file = dedup_config_dict.get("cache_file", str(project_root / "data" / "dedup_cache.json"))
        
        dedup_config = DedupFilterConfig(
            enabled=dedup_enabled,
            similarity_threshold=dedup_threshold,
            exact_dedup=dedup_exact,
            fuzzy_dedup=dedup_fuzzy,
            min_length=dedup_min_length,
            cache_file=cache_file
        )
        self.dedup_filter = DedupFilter(dedup_config)
        
        logger.info(f"[Pipeline] 过滤器初始化完成 - 敏感词: {sensitive_enabled}, 去重: {dedup_enabled}")

    def _init_notifiers(self):
        """初始化通知器"""
        notification_config = self.config.get("notifications", {})
        self.notifiers = create_notifiers({"notifications": notification_config})
        names = [n.get_name() for n in self.notifiers]
        logger.info(f"[Pipeline] 通知器初始化完成: {names}")

    async def _notify(self, title: str, body: str, level: str = "info",
                       source_name: str = "", articles_count: int = 0,
                       duration: float = 0.0, data: dict | None = None):
        """发送通知到所有通知器"""
        msg = NotificationMessage(
            title=title, body=body, level=level,
            source_name=source_name, articles_count=articles_count,
            duration=duration, data=data or {}
        )
        results = []
        for notifier in self.notifiers:
            result = await notifier.notify(msg)
            results.append(result)
            if not result.success:
                logger.warning(f"[Pipeline] 通知失败 ({notifier.get_name()}): {result.error}")
        return results

    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.rewrite_processor = RewriteProcessor(self.config)
        await self.rewrite_processor.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        if self.rewrite_processor:
            await self.rewrite_processor.__aexit__(exc_type, exc_val, exc_tb)

    async def _apply_filters(self, content: Content) -> tuple[bool, str]:
        """
        应用过滤器
        
        参数：
            content: Content 对象
            
        返回：
            (should_block: bool, reason: str)
        """
        # 1. 敏感词过滤
        if self.sensitive_filter.config.enabled:
            text_to_check = f"{content.title}\n{content.content}"
            filter_result = self.sensitive_filter.process(text_to_check)
            
            if filter_result["action"] == "block":
                matched_words = ", ".join(filter_result["matched_words"])
                logger.warning(f"[过滤] 敏感词拦截: {content.title[:40]}... (匹配词: {matched_words})")
                return True, f"敏感词: {matched_words}"
            
            # 更新 content（可能已替换敏感词）
            if filter_result["has_sensitive"] and not filter_result["action"] == "block":
                # 非严格模式：替换敏感词后继续
                content.title = filter_result["filtered_text"].split("\n")[0] if "\n" in filter_result["filtered_text"] else content.title
                # 注意：这里简单处理，实际应该更精细地替换
        
        # 2. 去重过滤
        if self.dedup_filter.config.enabled:
            content_dict = {
                "title": content.title,
                "content": content.content
            }
            dedup_result = await self.dedup_filter.process(content_dict)
            
            if dedup_result["action"] == "block":
                similar_to = ", ".join(dedup_result["similar_to"][:3])
                logger.info(f"[过滤] 去重拦截: {content.title[:40]}... (相似: {similar_to})")
                return True, f"重复内容: {similar_to}"
        
        return False, ""

    async def process_url(self, url: str, rewrite: bool = True, strategy: RewriteStrategy | str | None = None, rewrite_config: RewriteConfig | None = None, seo: bool = False, limit: int | None = None) -> list[Article]:
        """
        处理单个RSS URL

        参数：
            url: RSS URL
            rewrite: 是否进行改写
            rewrite_config: 改写配置

        返回：
            Article 对象列表（最多 limit 篇）
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
            return []

        articles = []
        items = result["data"][:limit] if limit else result["data"]
        
        filtered_count = {"sensitive": 0, "dedup": 0}
        
        for content in items:
            logger.info(f"Collected: {content.title}")

            # === 过滤步骤 ===
            should_block, reason = await self._apply_filters(content)
            if should_block:
                if "敏感词" in reason:
                    filtered_count["sensitive"] += 1
                else:
                    filtered_count["dedup"] += 1
                continue

            # 改写
            if rewrite and self.rewrite_processor:
                _strat = strategy if isinstance(strategy, RewriteStrategy) else RewriteStrategy(strategy or "rewrite")
                _rewrite_config = rewrite_config or RewriteConfig(
                    strategy=_strat,
                    min_word_count=500,
                    max_word_count=5000,
                    target_word_count=3000
                )
                rewrite_result = await self.rewrite_processor.rewrite(content, _rewrite_config)

                if rewrite_result.success:
                    metadata = rewrite_result.metadata.copy() if rewrite_result.metadata else {}
                    metadata['original_content'] = content.content
                    metadata['original_title'] = content.title
                    metadata['original_author'] = getattr(content, 'author', '') or ''
                    article = Article(
                        id=getattr(rewrite_result.original_content, 'id', None) if rewrite_result.original_content else str(uuid.uuid4()),
                        title=rewrite_result.title or content.title,
                        original_title=content.title,
                        source=getattr(content, 'source_id', '') or content.source or '',
                        source_url=content.url if hasattr(content, 'url') else '',
                        author=rewrite_result.original_content.author if rewrite_result.original_content else "",
                        published_at=content.published_at,
                        content=rewrite_result.rewritten_content,
                        summary=rewrite_result.summary,
                        word_count=len(rewrite_result.rewritten_content),
                        metadata=metadata
                    )

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

                    articles.append(article)
                else:
                    logger.error(f"Rewrite failed: {rewrite_result.error}")
                    articles.append(Article.from_content(content))
            else:
                articles.append(Article(
                    id=content.id if hasattr(content, 'id') and content.id else str(uuid.uuid4()),
                    title=content.title,
                    content=content.content,
                    source=content.source_id if hasattr(content, 'source_id') else getattr(content, 'name', '') or '',
                    source_url=content.url if hasattr(content, 'url') else '',
                    published_at=getattr(content, 'published_at', None),
                    author=getattr(content, 'author', None) or getattr(content, 'name', None) or '',
                ))

        logger.info(f"[Pipeline] 过滤统计 - 敏感词: {filtered_count['sensitive']}, 去重: {filtered_count['dedup']}, 通过: {len(articles)}")
        return articles

    async def process_all_sources(
        self,
        rewrite: bool = True,
        translate: bool = False,
        target_language: str | None = None,
        seo: bool = False,
        formats: list[str] | None = None,
        limit_per_source: int | None = None,
        progress_callback: Optional[Callable] = None,
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
        total_filtered = {"sensitive": 0, "dedup": 0}

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
            "douyin_hot": self._parse_single_config,
            "wangyi": self._parse_single_config,
            "weibo_hot": self._parse_single_config,
            "xiaohongshu": self._parse_single_config,
            "wechat": self._parse_single_config,
            "sitemap": self._parse_single_config,
            "api": self._parse_single_config,
        }

        # 计算总源数（用于进度计算）
        total_sources = 0
        for source_type, parse_fn in source_configs_map.items():
            entries = parse_fn(source_type)
            if entries:
                total_sources += len(entries)

        current_source = 0

        for source_type, parse_fn in source_configs_map.items():
            entries = parse_fn(source_type)
            print(f"[DEBUG] process_all: {source_type} -> {len(entries) if entries else 0} entries")
            if not entries:
                continue

            for entry in entries:
                current_source += 1
                entry_name = entry.get("name", source_type)
                
                # 报告进度
                if progress_callback:
                    progress = int((current_source - 1) / total_sources * 100) if total_sources > 0 else 0
                    await progress_callback(current_source - 1, total_sources, f"正在采集: {entry_name}", progress)
                
                logger.info(f"[Pipeline] 采集源: {entry_name} ({source_type})")
                entry_name = entry.get("name", source_type)
                logger.info(f"[Pipeline] 采集源: {entry_name} ({source_type})")

                # Fix: filter invalid params, map max_items->max_results
                collect_kwargs = {k: v for k, v in entry.items() if k != 'name'}
                if 'max_items' in collect_kwargs:
                    collect_kwargs['max_results'] = collect_kwargs.pop('max_items')

                try:
                    collector = get_collector(
                        source_type,
                        config=entry,
                        proxy=self.proxy,
                        timeout=self.http_config.get("timeout", 30),
                    )
                    
                    # Fix: Inject limit_per_source into collect_kwargs (use max_results to be consistent)
                    if limit_per_source:
                        collect_kwargs['max_results'] = limit_per_source
                    
                    result: SourceResult = await collector.collect(**collect_kwargs)
                    logger.info(f'[process_source] {entry_name}: success={result.success}, collected={result.collected_count}, data_len={len(result.data) if result.data else 0}')

                    # 采集成功，转换为 Article
                    source_article_count = 0
                    for item_data in (result.data or []):
                        if limit_per_source and source_article_count >= limit_per_source:
                            break
                        source_article_count += 1
                        
                        # 创建 Content 对象用于过滤
                        content = Content(
                            id=str(uuid.uuid4()),
                            title=item_data.get("title", ""),
                            content=item_data.get("content", ""),
                            source_type=source_type,
                            source_id=entry_name,
                            url=item_data.get("url", ""),
                            author=item_data.get("author", ""),
                            published_at=item_data.get("published_at"),
                            summary=item_data.get("summary", ""),
                        )
                        
                        # === 过滤步骤 ===
                        should_block, reason = await self._apply_filters(content)
                        if should_block:
                            if "敏感词" in reason:
                                total_filtered["sensitive"] += 1
                            else:
                                total_filtered["dedup"] += 1
                            continue

                        article = Article(
                            id=content.id,
                            title=content.title,
                            content=content.content,
                            source=content.source_type,
                            source_url=content.url,
                            author=content.author,
                            published_at=content.published_at,
                            summary=content.summary,
                            word_count=len(content.content),
                        )

                        # 改写
                        if rewrite and self.rewrite_processor and article.word_count > 0:
                            try:
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
                                trans_config = TranslationConfig(
                                    target_language=translation_lang,
                                    tone=self.translation_config.get("tone", "casual"),
                                )
                                trans_result = await translator.translate(content, trans_config)
                                if trans_result.success:
                                    article.title = f"{article.title} ({translation_lang.value})"
                                    article.content = trans_result.translated_content
                                    article.word_count = len(trans_result.translated_content)
                            except Exception as e:
                                logger.warning(f"翻译失败（{article.title}）: {e}")

                        # SEO 优化
                        if seo and seo_processor and article.word_count > 0:
                            try:
                                seo_result = await seo_processor.optimize(content)
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

                    # 成功：追加到 source_results
                    source_results.append({
                        "source_name": entry_name,
                        "source_type": source_type,
                        "success": result.success,
                        "collected": result.collected_count,
                        "skipped": result.skipped_count,
                        "error": result.error,
                        "duration": result.duration,
                    })
                    print(f"  [OK] {entry_name}: 采集 {result.collected_count} 篇")
                    
                    # 报告进度（完成当前源）
                    if progress_callback:
                        progress = int(current_source / total_sources * 100) if total_sources > 0 else 100
                        await progress_callback(current_source, total_sources, f"完成采集: {entry_name}", progress)

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
                    
                    # 报告进度（跳过当前源）
                    if progress_callback:
                        progress = int(current_source / total_sources * 100) if total_sources > 0 else 100
                        await progress_callback(current_source, total_sources, f"跳过: {entry_name}", progress)

        elapsed = time.time() - start
        success_sources = sum(1 for r in source_results if r["success"])

        # Cleanup SEO processor
        if seo_processor:
            await seo_processor.__a_exit__(None, None, None)

        print(f"\n{'=' * 60}")
        print(f"汇总")
        print(f"{'=' * 60}")
        print(f"  数据源总数: {len(source_results)}")
        print(f"  成功: {success_sources}")
        print(f"  跳过: {total_skipped}")
        print(f"  过滤 - 敏感词: {total_filtered['sensitive']}, 去重: {total_filtered['dedup']}")
        print(f"  文章总数: {len(all_articles)}")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"{'=' * 60}")

        # 发送采集完成通知
        failed_names = [r["source_name"] for r in source_results if not r["success"]]
        notify_level = "success" if total_skipped == 0 else ("warning" if total_skipped < success_sources else "error")
        notify_body_lines = [
            f"数据源: {len(source_results)} 个（成功 {success_sources}，跳过 {total_skipped}）",
            f"文章: {len(all_articles)} 篇",
            f"过滤: 敏感词 {total_filtered['sensitive']} 篇，去重 {total_filtered['dedup']} 篇",
            f"耗时: {elapsed:.1f}s",
        ]
        if failed_names:
            notify_body_lines.append(f"失败源: {', '.join(failed_names)}")
        await self._notify(
            title="采集任务完成",
            body="\n".join(notify_body_lines),
            level=notify_level,
            articles_count=len(all_articles),
            duration=elapsed,
            data={"failed_sources": failed_names, "filtered": total_filtered}
        )

        return {
            "articles": all_articles,
            "source_results": source_results,
            "summary": {
                "total_sources": len(source_results),
                "success": success_sources,
                "skipped": total_skipped,
                "filtered": total_filtered,
                "total_articles": len(all_articles),
                "elapsed": elapsed,
            }
        }

    async def process_source(
        self,
        source_type: str,
        rewrite: bool = True,
        translate: bool = False,
        target_language: str | None = None,
        formats: list[str] | None = None,
        limit_per_source: int | None = None,
        progress_callback: Optional[Callable] = None,
    ) -> dict[str, Any]:
        """
        采集单个数据源（用于 YouTube 等独立采集按钮）

        参数：
            source_type: 源类型（如 youtube, twitter 等）
            rewrite: 是否改写
            translate: 是否翻译
            target_language: 目标语言
            formats: 导出格式列表
            limit_per_source: 最大采集数

        返回：
            {
                "articles": [...],
                "summary": {
                    "total_sources": 1,
                    "success": 1,
                    "total_articles": 5,
                }
            }
        """
        import time
        all_articles: list[Article] = []
        source_results: list[dict] = []
        start = time.time()

        # 翻译器
        translator = None
        translation_lang = None
        if translate and self.translation_config.get("enabled", False):
            lang_code = target_language or self.translation_config.get("default_language", "EN")
            translation_lang = TranslationLanguage(lang_code)
            translator = TranslatorProcessor(self.config)

        # 获取解析器
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

        parse_fn = source_configs_map.get(source_type)
        if not parse_fn:
            return {"articles": [], "summary": {"total_sources": 0, "success": 0, "total_articles": 0}}

        entries = parse_fn(source_type)
        if not entries:
            return {"articles": [], "summary": {"total_sources": 0, "success": 0, "total_articles": 0, "message": f"未配置 {source_type} 源"}}

        total_entries = len(entries)
        current_entry = 0

        for entry in entries:
            current_entry += 1
            entry_name = entry.get("name", source_type)
            
            # 报告进度
            if progress_callback:
                progress = int((current_entry - 1) / total_entries * 100) if total_entries > 0 else 0
                await progress_callback(current_entry - 1, total_entries, f"正在采集: {entry_name}", progress)
            
            try:
                collector = get_collector(
                    source_type,
                    config=entry,
                    proxy=self.proxy,
                    timeout=self.http_config.get("timeout", 30),
                )
                
                # Fix: filter invalid params, map max_items->max_results
                collect_kwargs = {k: v for k, v in entry.items() if k != 'name'}
                if 'max_items' in collect_kwargs:
                    collect_kwargs['max_results'] = collect_kwargs.pop('max_items')
                
                # Fix: Inject limit_per_source into collect_kwargs for process_contents()
                if limit_per_source:
                    collect_kwargs['max_results'] = limit_per_source
                
                result: SourceResult = await collector.collect(**collect_kwargs)
                logger.info(f'[process_source] {entry_name}: success={result.success}, collected={result.collected_count}, data_len={len(result.data) if result.data else 0}')

                source_results.append({
                    "source_name": entry_name,
                    "success": result.success,
                    "collected": result.collected_count,
                    "error": result.error,
                })
                
                # 报告进度（完成当前条目）
                if progress_callback:
                    progress = int(current_entry / total_entries * 100) if total_entries > 0 else 100
                    await progress_callback(current_entry, total_entries, f"完成采集: {entry_name}", progress)
                
                if result.success and result.data:
                    # result.data 是 dict 列表，需要转为 Content 对象
                    from content_aggregator.models import Content
                    contents = []
                    for d in (result.data[:limit_per_source] if limit_per_source else result.data):
                        content = Content(
                            id=d.get("id", str(uuid.uuid4())),
                            source_id=source_type,
                            source_type=source_type,
                            url=d.get("url", ""),
                            title=d.get("title", ""),
                            content=d.get("content", ""),
                            author=d.get("author", ""),
                            published_at=d.get("published_at"),
                            summary=d.get("summary", ""),
                            metadata=d.get("metadata", {}),
                        )
                        contents.append(content)
                    
                    # 过滤和改写由 process_contents 统一处理
                    articles = await self.process_contents(contents, rewrite=rewrite, progress_callback=progress_callback)
                    logger.info(f'[process_source] {entry_name}: {len(contents)} contents -> {len(articles)} articles')
                    all_articles.extend(articles)

            except Exception as e:
                logger.error(f"采集失败 [{entry_name}]: {e}")
                source_results.append({"source_name": entry_name, "success": False, "error": str(e)})
                
                # 报告进度（跳过当前条目）
                if progress_callback:
                    progress = int(current_entry / total_entries * 100) if total_entries > 0 else 100
                    await progress_callback(current_entry, total_entries, f"跳过: {entry_name}", progress)

        elapsed = time.time() - start
        success_sources = sum(1 for r in source_results if r.get("success"))
        return {
            "articles": all_articles,
            "source_results": source_results,
            "summary": {
                "total_sources": len(source_results),
                "success": success_sources,
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
        entries = []

        # YouTube 搜索关键词
        if source_type == "youtube":
            search_queries = source_cfg.get("search_queries", [])
            if search_queries:
                search_order = source_cfg.get("search_order", "relevance")
                search_limit = source_cfg.get("search_limit", 10)
                for query in search_queries:
                    if isinstance(query, str) and query.strip():
                        entry = dict(source_cfg)
                        entry["search_query"] = query.strip()
                        entry["order"] = search_order
                        entry["max_results"] = search_limit
                        entry["name"] = f"YouTube搜索: {query.strip()}"
                        entry["max_items"] = search_limit
                        entries.append(entry)

        # 网易新闻频道列表
        if source_type == "wangyi":
            channels = source_cfg.get("channels", ["news", "ent", "tech"])
            limit = source_cfg.get("limit", 10)
            for ch in channels:
                if isinstance(ch, str) and ch.strip():
                    entry = dict(source_cfg)
                    entry["channels"] = [ch.strip()]
                    entry["name"] = f"网易{ch.strip()}"
                    entry["max_items"] = limit
                    entries.append(entry)

        # 抖音热点/微博热点：直接作为单个源（无子列表）
        if source_type in ("douyin_hot", "weibo_hot"):
            if source_cfg.get("enabled", True):
                entry = dict(source_cfg)
                entry["name"] = {"douyin_hot": "抖音热点榜", "weibo_hot": "微博热点"}.get(source_type, source_type)
                entry["max_items"] = source_cfg.get("limit", 20)
                entries.append(entry)
                return entries
            return []

        # 频道/用户/账号列表
        for list_key in ["channels", "users", "accounts", "sites", "endpoints"]:
            items = source_cfg.get(list_key, [])
            if items:
                for item in items:
                    if isinstance(item, str):
                        entry = dict(source_cfg)
                        # 频道 ID 字符串 → channel_id 参数
                        if list_key == "channels":
                            entry["channel_id"] = item
                        else:
                            entry["base_url"] = item
                        entry["name"] = item
                        entry["max_items"] = 20
                        entries.append(entry)
                        continue

                    entry = dict(source_cfg)  # 复制全局配置（api_key/cookie 等）
                    entry.update(item)  # 用单项配置覆盖
                    entry["name"] = item.get("name", source_type)
                    entry["max_items"] = item.get("max_items", 20)
                    entries.append(entry)

        # 如果有 entries 直接返回
        if entries:
            return entries

        # 如果有 api_url 或 base_url 等直接字段，视为单个源
        if source_cfg.get("api_url") or source_cfg.get("base_url"):
            return [{**source_cfg, "name": source_cfg.get("name", source_type), "max_items": 20}]

        return []

    async def process_contents(self, contents: list[Content], rewrite: bool = True, progress_callback: Optional[Callable] = None) -> list[Article]:
        """
        处理内容列表

        参数：
            contents: Content 对象列表
            rewrite: 是否进行改写
            progress_callback: 进度回调函数

        返回：
            Article 对象列表
        """
        articles = []
        total = len(contents)
        current = 0

        for content in contents:
            current += 1
            try:
                # 报告进度（开始处理当前文章）
                if progress_callback:
                    progress = int((current - 1) / total * 100) if total > 0 else 0
                    await progress_callback(current - 1, total, f"正在改写: {content.title[:30]}", progress)

                # === 过滤步骤 ===
                should_block, reason = await self._apply_filters(content)
                if should_block:
                    logger.info(f"[process_contents] 过滤跳过: {content.title[:40]} ({reason})")
                    continue

                # 改写
                if rewrite and self.rewrite_processor:
                    logger.info(f"[process_contents] Rewriting: {content.title[:60]}")
                    rewrite_result = await self.rewrite_processor.rewrite(content, progress_callback=progress_callback)
                    rewritten_text = rewrite_result.rewritten_content if rewrite_result.success else ""
                    # 如果改写结果为空，则使用原文内容（避免短描述改写后无内容）
                    final_content = rewritten_text if rewritten_text else content.content
                    metadata = (rewrite_result.metadata.copy() if rewrite_result.metadata else {}) if rewrite_result.success else {}
                    metadata['original_content'] = content.content
                    metadata['original_title'] = content.title
                    metadata['original_author'] = content.author
                    article = Article(
                        id=str(uuid.uuid4()),
                        title=rewrite_result.title or content.title if rewrite_result.success else content.title,
                        original_title=content.title,
                        source=content.source_id,
                        source_url=content.url,
                        author=content.author,
                        published_at=content.published_at,
                        content=final_content,
                        summary=rewrite_result.summary if rewrite_result.success else "",
                        word_count=len(final_content),
                        metadata=metadata
                    )
                    articles.append(article)
                    logger.info(f"[process_contents] Done: {content.title[:60]} -> {len(final_content)} chars")

                    # 报告进度（完成当前文章）
                    if progress_callback:
                        progress = int(current / total * 100) if total > 0 else 100
                        await progress_callback(current, total, f"完成改写: {content.title[:30]}", progress)

                else:
                    article = Article.from_content(content)
                    articles.append(article)
            except Exception as e:
                logger.error(f"[process_contents] Error processing '{content.title[:60]}': {e}", exc_info=True)
                # fallback: 用原文直接创建文章
                try:
                    article = Article.from_content(content)
                    articles.append(article)
                except Exception:
                    logger.error(f"[process_contents] Fallback also failed for '{content.title[:60]}'")

        logger.info(f"[process_contents] Total: {len(contents)} contents -> {len(articles)} articles")
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
    return str(exporter.export(article, format_type))
