"""文章/改写历史模型 — Article ORM 映射"""

import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Article(Base):
    """文章/改写历史表 — 每次改写操作生成一条记录"""

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 来源类型: url / text / file
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    # 源内容（原始文章全文）
    source_content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # 源 URL（当 source_type=url 时有值）
    source_url: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # 改写风格: 轻松易懂 / 正式严谨 / 吸引眼球 / 深度分析
    rewrite_style: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    # 改写长度: keep / compress / expand
    rewrite_length: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    # 改写结果内容
    result_content: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # 原文词数
    word_count_original: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # 改写后词数
    word_count_result: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 关联
    user: Mapped["User"] = relationship("User", back_populates="articles")
    publish_logs: Mapped[list["PublishLog"]] = relationship(
        "PublishLog", back_populates="article", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Article(id={self.id}, source_type={self.source_type!r}, style={self.rewrite_style!r})>"
