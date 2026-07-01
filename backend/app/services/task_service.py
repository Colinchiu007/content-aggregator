"""Task cancellation service — cancel long-running operations."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task

logger = logging.getLogger(__name__)

# Tasks in these states can be cancelled
CANCELLABLE_STATUSES = {"pending", "running"}


async def cancel_task(task_id: str, db: AsyncSession) -> dict:
    """Cancel a task by its ID.

    Args:
        task_id: Task identifier
        db: Database session

    Returns:
        dict with updated task status

    Raises:
        ValueError: If task not found or cannot be cancelled
    """
    # Find task
    task = await db.get(Task, task_id)
    if task is None:
        raise ValueError("task_not_found")

    # Check if cancellable
    if task.status not in CANCELLABLE_STATUSES:
        raise ValueError(
            f"task_not_cancellable",
        )

    # Determine target status
    if task.status == "running":
        new_status = "cancelling"
        # Revoke Celery task if present
        if task.celery_task_id:
            _revoke_celery_task(task.celery_task_id)
    else:
        new_status = "cancelled"

    # Update DB
    task.status = new_status
    await db.flush()

    logger.info("Task %s cancelled: %s → %s", task_id, task.status, new_status)
    return {"status": new_status}


def _revoke_celery_task(celery_task_id: str) -> None:
    """Revoke a Celery task if celery is available."""
    try:
        from app.celery_app import celery_app

        celery_app.control.revoke(celery_task_id, terminate=False)
        logger.info("Revoked Celery task: %s", celery_task_id)
    except (ImportError, AttributeError) as exc:
        logger.warning("Celery not available, skip revoke: %s", exc)
