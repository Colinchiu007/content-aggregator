"""竞品监控 — 监控源 ORM 模型"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MonitorSource(Base):
    """监控源表 — 用户添加的竞品账号"""

    __tablename__ = "monitor_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="监控源名称")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="wechat / zhihu / url")
    identifier: Mapped[str] = mapped_column(Text, nullable=False, comment="公众号ID / 知乎UID / URL")
    schedule_cron: Mapped[str | None] = mapped_column(String(20), nullable=True, comment="自定义采集频率 (cron)")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关联
    articles: Mapped[list["MonitorArticle"]] = relationship(
        "MonitorArticle", back_populates="source", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<MonitorSource(id={self.id}, name={self.name!r}, type={self.source_type!r})>"
