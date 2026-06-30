"""多平台发布服务 — 任务创建与状态查询

Phase 1: 为每个平台创建 PublishLog 记录并异步派发 Celery 任务执行实际发布。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.article import Article
from app.models.publish_log import PublishLog
from app.core.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _get_celery_app():
    """懒加载 Celery 实例"""
    try:
        from app.tasks import celery_app
        return celery_app
    except ImportError:
        logger.warning("Celery 未配置，发布任务将不会异步执行")
        return None


async def create_publish_tasks(
    article_id: UUID,
    user_id: UUID,
    platforms: list[str],
) -> dict:
    """为一篇文章创建多个平台的发布任务

    - 验证文章存在且已完成改写
    - 为每个平台创建 PublishLog（初始状态 pending）
    - 异步派发 Celery 任务执行实际发布
    - 返回包含 task_id 和平台列表的响应

    Args:
        article_id: 文章 ID
        user_id: 用户 ID
        platforms: 目标平台列表

    Returns:
        dict: {"task_id": str, "platforms": [...], "message": "..."}

    Raises:
        NotFoundError: 文章不存在或未完成改写
    """
    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article:
            raise NotFoundError(f"文章不存在: {article_id}")
        if not article.result_content:
            raise NotFoundError(f"文章尚未完成 AI 改写，无法发布: {article_id}")

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

    # 异步派发 Celery 任务
    task_ids = []
    celery_app = _get_celery_app()
    if celery_app is not None:
        try:
            from app.tasks import ca_publish_to_platform
            for platform in platforms:
                async_result = ca_publish_to_platform.delay(
                    article_id=str(article_id),
                    platform=platform,
                )
                task_ids.append(str(async_result.id))
        except Exception as e:
            logger.warning(f"派发 Celery 任务失败（发布日志已创建）: {e}")

    logger.info(
        f"发布任务已创建: article={article_id}, "
        f"platforms={platforms}, celery_tasks={task_ids}"
    )
    return {
        "task_id": str(article_id),
        "platforms": platforms,
        "task_ids": task_ids,
        "message": f"已为 {len(platforms)} 个平台创建发布任务",
    }


async def get_publish_status(article_id: UUID) -> dict:
    """查询某篇文章的发布状态"""
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


async def _execute_platform_publish(article_id: str, platform: str) -> dict:
    """执行单个平台的实际发布操作 — 调用 orchestrator publish API

    Phase 2: 集成了 orchestrator 发布 API 调用。
    通过环境变量 ORCHESTRATOR_BASE_URL 配置 orchestrator 地址。

    Args:
        article_id: 文章 ID (UUID 字符串)
        platform: 目标平台 (wechat / zhihu / toutiao 等)

    Returns:
        dict: {status, article_id, platform, orchestrator_task_id?, error?}
    """
    import uuid as _uuid

    article_uuid = _uuid.UUID(article_id)
    settings = get_settings()
    orchestrator_url = f"{settings.ORCHESTRATOR_BASE_URL}/api/jobs/publish"

    # 先更新本地 PublishLog 状态为 running
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishLog).where(
                PublishLog.article_id == article_uuid,
                PublishLog.platform == platform,
            )
        )
        log = result.scalar_one_or_none()
        if not log:
            logger.warning(f"未找到发布日志: article={article_id}, platform={platform}")
            return {"status": "not_found", "article_id": article_id, "platform": platform}

        # 通过 orchestrator API 发布
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    orchestrator_url,
                    json={
                        "article_id": article_id,
                        "platforms": [platform],
                    },
                    headers={
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                orchestrator_result = resp.json()

            log.status = "success"
            log.published_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(
                f"发布成功: article={article_id}, platform={platform}, "
                f"orchestrator_task={orchestrator_result.get('task_id')}"
            )
            return {
                "status": "success",
                "article_id": article_id,
                "platform": platform,
                "orchestrator_task_id": orchestrator_result.get("task_id"),
            }

        except httpx.HTTPStatusError as e:
            error_msg = f"Orchestrator 返回错误: HTTP {e.response.status_code}"
            log.status = "failed"
            log.error_message = error_msg
            await db.commit()
            logger.error(f"发布失败: {error_msg}")
            return {"status": "failed", "article_id": article_id, "platform": platform, "error": error_msg}

        except httpx.RequestError as e:
            error_msg = f"无法连接到 Orchestrator: {e}"
            log.status = "failed"
            log.error_message = error_msg
            await db.commit()
            logger.error(f"发布失败: {error_msg}")
            return {"status": "failed", "article_id": article_id, "platform": platform, "error": error_msg}
