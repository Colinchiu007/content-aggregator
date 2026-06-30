"""竞品监控 API 路由 — MonitorArticle 列表 + 标记已读 + 一键改写

Phase A: JWT payload dict，使用 sqlalchemy select 方式
"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.monitor_article import MonitorArticle
from app.models.monitor_source import MonitorSource
from app.schemas.monitor import (
    MonitorArticleItem,
    MonitorArticleDetail,
    MonitorArticleRewriteRequest,
)

router = APIRouter(prefix="/monitor-articles", tags=["竞品监控"])


@router.get("/", response_model=dict)
async def list_monitor_articles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    source_id: UUID = Query(None, description="按监控源筛选"),
    is_read: bool = Query(None, description="按已读状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """获取当前用户的监控文章列表（分页 + 筛选）"""
    user_id = current_user.get("sub")

    # 构建查询 — 只返回用户有权访问的文章
    # 通过 MonitorSource 关联确保用户只能看到自己的文章
    conditions = [MonitorArticle.source_id == MonitorSource.id,
                  MonitorSource.user_id == user_id]
    if source_id:
        conditions.append(MonitorArticle.source_id == source_id)
    if is_read is not None:
        conditions.append(MonitorArticle.is_read == is_read)

    # 计数
    count_result = await db.execute(
        select(func.count(MonitorArticle.id))
        .select_from(MonitorArticle)
        .join(MonitorSource, MonitorArticle.source_id == MonitorSource.id)
        .where(*conditions)
    )
    total = count_result.scalar() or 0

    # 查询
    offset = (page - 1) * page_size
    result = await db.execute(
        select(MonitorArticle)
        .join(MonitorSource, MonitorArticle.source_id == MonitorSource.id)
        .where(*conditions)
        .order_by(MonitorArticle.collected_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    articles = result.scalars().all()

    return {
        "items": [MonitorArticleItem.model_validate(a) for a in articles],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


@router.post("/{article_id}/read", response_model=MonitorArticleItem)
async def mark_as_read(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MonitorArticle:
    """标记监控文章为已读"""
    user_id = current_user.get("sub")

    # 验证文章属于当前用户
    result = await db.execute(
        select(MonitorArticle)
        .join(MonitorSource, MonitorArticle.source_id == MonitorSource.id)
        .where(
            MonitorArticle.id == article_id,
            MonitorSource.user_id == user_id,
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="监控文章不存在",
        )

    article.is_read = True
    await db.flush()
    await db.refresh(article)
    return article


@router.post("/{article_id}/rewrite")
async def rewrite_monitor_article(
    article_id: UUID,
    body: MonitorArticleRewriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """一键改写监控文章（异步触发 Celery 任务）"""
    user_id = current_user.get("sub")

    # 验证文章属于当前用户
    result = await db.execute(
        select(MonitorArticle)
        .join(MonitorSource, MonitorArticle.source_id == MonitorSource.id)
        .where(
            MonitorArticle.id == article_id,
            MonitorSource.user_id == user_id,
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="监控文章不存在",
        )

    # 异步触发改写任务
    from app.tasks import celery_app, ca_rewrite_article
    if celery_app is not None:
        task = ca_rewrite_article.delay(str(article_id), style=body.style)
        return {"status": "queued", "task_id": task.id, "article_id": str(article_id), "style": body.style}
    else:
        return {"status": "unavailable", "message": "Celery 不可用，请稍后重试"}
