"""竞品监控 API 路由 — MonitorSource CRUD

Phase A: JWT payload dict，使用 sqlalchemy select 方式（与 articles.py 完全一致）
"""

import math
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.monitor_source import MonitorSource
from app.schemas.monitor import (
    MonitorSourceCreate,
    MonitorSourceUpdate,
    MonitorSourceResponse,
    MonitorSourceListItem,
)

router = APIRouter(prefix="/monitors", tags=["竞品监控"])


@router.get("/", response_model=dict)
async def list_monitors(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: str = Query(None, description="搜索关键词（名称/标识符）"),
    source_type: str = Query(None, description="过滤监控源类型: wechat / zhihu / url"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """获取当前用户的监控源列表（分页 + 搜索 + 筛选）"""
    user_id = current_user.get("sub")

    # 构建查询条件
    conditions = [MonitorSource.user_id == user_id]
    if search:
        conditions.append(
            or_(
                MonitorSource.name.ilike(f"%{search}%"),
                MonitorSource.identifier.ilike(f"%{search}%"),
            )
        )
    if source_type:
        conditions.append(MonitorSource.source_type == source_type)

    # 计数
    count_result = await db.execute(
        select(func.count(MonitorSource.id)).where(*conditions)
    )
    total = count_result.scalar() or 0

    # 查询
    offset = (page - 1) * page_size
    result = await db.execute(
        select(MonitorSource)
        .where(*conditions)
        .order_by(MonitorSource.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    monitors = result.scalars().all()

    return {
        "items": [MonitorSourceListItem.model_validate(m) for m in monitors],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


@router.post("/", response_model=MonitorSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_monitor(
    body: MonitorSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MonitorSource:
    """创建监控源"""
    user_id = current_user.get("sub")

    monitor = MonitorSource(
        user_id=user_id,
        name=body.name,
        source_type=body.source_type,
        identifier=body.identifier,
        schedule_cron=body.schedule_cron,
        is_active=body.is_active if body.is_active is not None else True,
    )
    db.add(monitor)
    await db.flush()
    await db.refresh(monitor)
    return monitor


@router.get("/{monitor_id}", response_model=MonitorSourceResponse)
async def get_monitor(
    monitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MonitorSource:
    """获取单个监控源详情"""
    user_id = current_user.get("sub")
    result = await db.execute(
        select(MonitorSource).where(
            MonitorSource.id == monitor_id,
            MonitorSource.user_id == user_id,
        )
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="监控源不存在",
        )
    return monitor


@router.put("/{monitor_id}", response_model=MonitorSourceResponse)
async def update_monitor(
    monitor_id: UUID,
    body: MonitorSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MonitorSource:
    """更新监控源"""
    user_id = current_user.get("sub")
    result = await db.execute(
        select(MonitorSource).where(
            MonitorSource.id == monitor_id,
            MonitorSource.user_id == user_id,
        )
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="监控源不存在",
        )

    # 更新可修改字段
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(monitor, field, value)

    await db.flush()
    await db.refresh(monitor)
    return monitor


@router.delete("/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitor(
    monitor_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    """删除监控源（同时级联删除关联的监控文章）"""
    user_id = current_user.get("sub")
    result = await db.execute(
        select(MonitorSource).where(
            MonitorSource.id == monitor_id,
            MonitorSource.user_id == user_id,
        )
    )
    monitor = result.scalar_one_or_none()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="监控源不存在",
        )

    await db.delete(monitor)
    await db.flush()
