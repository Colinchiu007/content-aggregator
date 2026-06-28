"""Task API route — cancel long-running operations."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.services.task_service import cancel_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def cancel_task_endpoint(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancel a pending or running task.

    - pending: marked as cancelled immediately
    - running: marked as cancelling (Celery task revoked if applicable)
    - completed/failed: returns 400 (不可取消)
    """
    try:
        return await cancel_task(task_id=task_id, db=db)
    except ValueError as e:
        msg = str(e)
        if msg == "task_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任务不存在",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务无法取消（仅支持 pending/running 状态的任务）",
        )
