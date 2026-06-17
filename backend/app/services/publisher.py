"""多平台发布服务 — 任务创建与状态查询

当前版本为 MVP 阶段，发布逻辑预留接口。
后续 Phase 2 会集成实际的平台 API 调用（微信公众号、知乎等）。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.article import Article
from app.models.publish_log import PublishLog
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def create_publish_tasks(
    article_id: UUID,
    user_id: UUID,
    platforms: list[str],
) -> dict:
    """为一篇文章创建多个平台的发布任务

    Args:
        article_id: 文章 ID
        user_id: 用户 ID
        platforms: 目标平台列表

    Returns:
        dict: {"task_id": str(article_id), "platforms": [...], "message": "..."}

    Raises:
        NotFoundError: 文章不存在或未完成改写
    """
    async with AsyncSessionLocal() as db:
        # 验证文章存在且有改写结果
        article = await db.get(Article, article_id)
        if not article:
            raise NotFoundError(f"文章不存在: {article_id}")
        if not article.result_content:
            raise NotFoundError(f"文章尚未完成 AI 改写，无法发布: {article_id}")

        # 为每个平台创建一条 publish_log（初始状态 pending）
        now = datetime.now(timezone.utc)
        for platform in platforms:
            log = PublishLog(
                user_id=user_id,
                article_id=article_id,
                platform=platform,
                status="pending",
                created_at=now,
            )
            db.add(log)

        await db.commit()

    logger.info(f"发布任务已创建: article={article_id}, platforms={platforms}")
    return {
        "task_id": str(article_id),
        "platforms": platforms,
        "message": f"已为 {len(platforms)} 个平台创建发布任务",
    }


async def get_publish_status(article_id: UUID) -> dict:
    """查询某篇文章的发布状态

    Args:
        article_id: 文章 ID

    Returns:
        dict: {"task_id": ..., "logs": [...]}

    Raises:
        NotFoundError: 没有相关发布记录
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishLog)
            .where(PublishLog.article_id == article_id)
            .order_by(PublishLog.created_at.desc())
        )
        logs = result.scalars().all()

        if not logs:
            raise NotFoundError(f"未找到该文章的发布记录: {article_id}")

        return {
            "task_id": article_id,
            "logs": [
                {
                    "id": log.id,
                    "platform": log.platform,
                    "status": log.status,
                    "error_message": log.error_message,
                    "published_at": log.published_at,
                    "created_at": log.created_at,
                }
                for log in logs
            ],
        }
