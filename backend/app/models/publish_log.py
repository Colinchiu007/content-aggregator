"""发布日志模型 — PublishLog ORM 映射"""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PublishLog(Base):
    """发布日志表 — 记录每次发布到各平台的结果"""

    __tablename__ = "publish_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 发布平台: wechat / zhihu / toutiao / custom_webhook 等
    platform: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # 发布状态: pending / success / failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # 失败时的错误信息
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # 实际发布时间
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 关联
    user: Mapped["User"] = relationship("User", back_populates="publish_logs")
    article: Mapped["Article"] = relationship("Article", back_populates="publish_logs")

    def __repr__(self) -> str:
        return f"<PublishLog(id={self.id}, platform={self.platform!r}, status={self.status!r})>"
