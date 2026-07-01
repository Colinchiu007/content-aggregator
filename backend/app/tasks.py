"""
Content-Aggregator 异步任务定义
"""
import logging

logger = logging.getLogger(__name__)


def get_celery_app():
    """懒加载 Celery 实例"""
    try:
        from trendscope.crawler.celery_app import app
        return app
    except ImportError:
        logger.warning("trendscope 未安装，Celery 任务不可用")
        return None


# ── ca_rewrite_article: always defined (placeholder when Celery is unavailable) ──

def _rewrite_article_factory(celery_app):
    """创建 ca_rewrite_article Celery 任务（或占位函数）"""
    if celery_app is None:
        # Placeholder when Celery is not installed
        def placeholder_task(*args, **kwargs):
            logger.warning("ca_rewrite_article: Celery 不可用，任务无法执行")
            return None
        placeholder_task.delay = lambda *args, **kwargs: None
        placeholder_task.apply_async = lambda *args, **kwargs: None
        return placeholder_task

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="ca_rewrite_article")
    def ca_rewrite_article(self, article_id: str, style: str = "casual"):
        """异步执行 AI 改写"""
        import asyncio
        from app.services.rewrite import rewrite_content
        from app.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models.article import Article
        import uuid as _uuid

        logger.info(f"[ca_rewrite_article] 开始改写: article_id={article_id}, style={style}")
        try:
            async def _run():
                article_uuid = _uuid.UUID(article_id)
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(Article).where(Article.id == article_uuid)
                    )
                    article = result.scalar_one_or_none()
                    if not article or not article.source_content:
                        raise ValueError(f"文章不存在或内容为空: {article_id}")
                    rewrite_result = await rewrite_content(
                        content=article.source_content,
                        style=style,
                    )
                    article.rewrite_style = style
                    article.result_content = rewrite_result.result_content
            asyncio.run(_run())
            return {"status": "success", "article_id": article_id}
        except Exception as e:
            logger.error(f"[ca_rewrite_article] 改写失败: {e}")
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)

    return ca_rewrite_article


# ── ca_collect_monitors: 竞品监控定时采集 ──

def _collect_monitors_factory(celery_app):
    """创建 ca_collect_monitors Celery 任务（或占位函数）"""
    if celery_app is None:
        def placeholder_task(*args, **kwargs):
            logger.warning("ca_collect_monitors: Celery 不可用，任务无法执行")
            return None
        placeholder_task.delay = lambda *args, **kwargs: None
        placeholder_task.apply_async = lambda *args, **kwargs: None
        return placeholder_task

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="ca_collect_monitors")
    def ca_collect_monitors(self):
        """定时采集所有活跃监控源的最新文章"""
        import asyncio
        from datetime import datetime, timezone

        logger.info("[ca_collect_monitors] 开始采集监控源")
        try:
            async def _run():
                from app.database import AsyncSessionLocal
                from app.models.monitor_source import MonitorSource
                from app.models.monitor_article import MonitorArticle
                from sqlalchemy import select

                async with AsyncSessionLocal() as db:
                    # 查询所有活跃监控源
                    result = await db.execute(
                        select(MonitorSource).where(MonitorSource.is_active == True)  # noqa: E712
                    )
                    sources = result.scalars().all()
                    logger.info(f"[ca_collect_monitors] 发现 {len(sources)} 个活跃监控源")

                    total_new = 0
                    for source in sources:
                        try:
                            # Placeholder: 模拟采集逻辑
                            logger.info(
                                f"[ca_collect_monitors] 采集: source={source.name}, "
                                f"type={source.source_type}, id={source.id}"
                            )

                            # 更新 last_collected_at
                            source.last_collected_at = datetime.now(timezone.utc)

                        except Exception as e:
                            logger.error(
                                f"[ca_collect_monitors] 采集失败: source={source.name}, "
                                f"error={e}"
                            )

                    await db.commit()
                    return {
                        "status": "success",
                        "total_sources": len(sources),
                        "new_articles": total_new,
                    }

            result = asyncio.run(_run())
            logger.info(f"[ca_collect_monitors] 采集完成: {result}")
            return result
        except Exception as e:
            logger.error(f"[ca_collect_monitors] 采集失败: {e}")
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)

    return ca_collect_monitors



# ── ca_publish_to_wx: 平台发布任务 ──

def _publish_factory(celery_app):
    """创建 ca_publish_to_wx Celery 任务（或占位函数）"""
    if celery_app is None:
        def placeholder_task(*args, **kwargs):
            logger.warning("ca_publish_to_wx: Celery 不可用，任务无法执行")
            return None
        placeholder_task.delay = lambda *args, **kwargs: None
        placeholder_task.apply_async = lambda *args, **kwargs: None
        return placeholder_task

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="ca_publish_to_wx")
    def ca_publish_to_wx(self, article_id: str, platform: str):
        """异步执行平台发布 — 通过 orchestrator API 转发"""
        import asyncio
        from app.services.publisher import _execute_platform_publish

        logger.info(f"[ca_publish_to_wx] 开始发布: article_id={article_id}, platform={platform}")
        try:
            result = asyncio.run(_execute_platform_publish(article_id, platform))
            logger.info(f"[ca_publish_to_wx] 发布完成: {result}")
            return result
        except Exception as e:
            logger.error(f"[ca_publish_to_wx] 发布失败: {e}")
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)

    return ca_publish_to_wx


# ── Module-level exports (always available) ──

celery_app = get_celery_app()
ca_rewrite_article = _rewrite_article_factory(celery_app)
ca_collect_monitors = _collect_monitors_factory(celery_app)
ca_publish_to_wx = _publish_factory(celery_app)
