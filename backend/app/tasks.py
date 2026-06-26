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


celery_app = get_celery_app()


if celery_app is not None:

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
                    article.word_count_result = rewrite_result.word_count
                    await db.commit()
                return {"status": "success", "article_id": article_id}

            result = asyncio.run(_run())
            logger.info(f"[ca_rewrite_article] 改写完成: article_id={article_id}")
            return result
        except Exception as e:
            logger.error(f"[ca_rewrite_article] 改写失败: {e}")
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="ca_publish_to_wx")
    def ca_publish_to_wx(self, article_id: str, platform: str = "weixin_article"):
        """异步发布到指定平台"""
        import asyncio
        from app.services.publisher import _execute_platform_publish

        logger.info(f"[ca_publish_to_wx] 开始发布: article_id={article_id}, platform={platform}")
        try:
            result = asyncio.run(_execute_platform_publish(article_id, platform))
            logger.info(f"[ca_publish_to_wx] 发布完成: article_id={article_id}, platform={platform}")
            return {"status": "success", "article_id": article_id, "platform": platform}
        except Exception as e:
            logger.error(f"[ca_publish_to_wx] 发布失败: {e}")
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)
