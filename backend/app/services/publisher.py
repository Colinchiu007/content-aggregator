"""多平台发布服务 — 任务创建与状态查询

Phase 1: 为每个平台创建 PublishLog 记录并异步派发 Celery 任务执行实际发布。
Phase 2: _execute_platform_publish 通过 orchestrator API 转发发布请求。
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select

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
            from app.tasks import ca_publish_to_wx
            for platform in platforms:
                async_result = ca_publish_to_wx.delay(
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
    """执行单个平台的实际发布操作

    通过 orchestrator API（POST /api/jobs/publish）将发布请求转发到对应的发布模块。
    orchestrator 不可达时标记为 failed 但不抛出异常（允许 Celery 重试机制处理）。

    Args:
        article_id: 文章 UUID 字符串
        platform: 目标平台标识

    Returns:
        dict: {"status": str, "article_id": str, "platform": str, "orchestrator_task_id": str | None}
    """
    import uuid as _uuid

    from app.config import get_settings

    settings = get_settings()
    orchestrator_url = settings.ORCHESTRATOR_API_URL.rstrip("/")

    article_uuid = _uuid.UUID(article_id)

    # 调用 orchestrator 发布 API
    orchestrator_task_id = None
    publish_ok = False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{orchestrator_url}/api/jobs/publish",
                json={
                    "article_id": article_id,
                    "platforms": [platform],
                },
            )
            resp.raise_for_status()
            result_data = resp.json()
            orchestrator_task_id = result_data.get("task_id")
            publish_ok = True
            logger.info(
                "Orchestrator 发布成功: article=%s, platform=%s, task_id=%s",
                article_id, platform, orchestrator_task_id,
            )
    except httpx.RequestError as e:
        logger.error(
            "Orchestrator 不可达: url=%s, article=%s, platform=%s, error=%s",
            orchestrator_url, article_id, platform, e,
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            "Orchestrator 返回错误: status=%s, article=%s, platform=%s, body=%s",
            e.response.status_code, article_id, platform, e.response.text,
        )
    except Exception as e:
        logger.exception(
            "调用 Orchestrator 发布 API 时发生未知异常: article=%s, platform=%s",
            article_id, platform,
        )

    status_val = "success" if publish_ok else "failed"

    # 更新 PublishLog 状态
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PublishLog).where(
                PublishLog.article_id == article_uuid,
                PublishLog.platform == platform,
            )
        )
        log = result.scalar_one_or_none()
        if not log:
            logger.warning("未找到发布日志: article=%s, platform=%s", article_id, platform)
            return {
                "status": "not_found",
                "article_id": article_id,
                "platform": platform,
                "orchestrator_task_id": orchestrator_task_id,
            }

        log.status = status_val
        log.error_message = None if publish_ok else f"Orchestrator API 调用失败"
        if publish_ok:
            log.published_at = datetime.now(timezone.utc)
        await db.commit()

    return {
        "status": status_val,
        "article_id": article_id,
        "platform": platform,
        "orchestrator_task_id": orchestrator_task_id,
    }
