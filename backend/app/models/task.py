"""Task ORM model — tracks cancellable long-running operations."""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Task(Base):
    """可取消的任务记录 — 采集/改写/发布等长耗时操作

    状态机:
        pending → cancelled
        running → cancelling → cancelled
        completed/failed → (不可取消)
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # task_type: collect / rewrite / publish
    task_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    # 状态: pending / running / cancelling / cancelled / completed / failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # 关联的 Celery task id（运行时设置）
    celery_task_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    # 关联的业务对象 ID（article_id / publish_log_id 等）
    ref_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    error: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, type={self.task_type!r}, status={self.status!r})>"
