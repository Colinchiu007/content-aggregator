"""
内容数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Content:
    """
    原始内容数据模型
    
    属性：
        id: 内容唯一标识（UUID）
        source_id: 数据源ID
        source_type: 数据源类型（rss/web/custom等）
        url: 原文链接
        title: 标题
        content: 正文内容
        summary: 摘要
        author: 作者
        published_at: 发布时间
        metadata: 扩展元数据
        raw_data: 原始数据（保持灵活性）
    """
    id: str
    source_id: str
    source_type: str
    url: str = ""
    title: str = ""
    content: str = ""
    summary: str = ""
    author: str = ""
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_data: Any = None


@dataclass
class Article:
    """
    处理后的文章数据模型（用于输出）
    
    属性：
        id: 文章唯一标识（UUID）
        title: 标题
        original_title: 原文标题
        source: 来源名称
        source_url: 原文链接
        author: 作者
        published_at: 发布时间
        content: 正文内容（改写后）
        summary: 摘要
        tags: 标签列表
        word_count: 字数
        metadata: 元数据
    """
    id: str = ""
    title: str = ""
    original_title: str = ""
    source: str = ""
    source_url: str = ""
    author: str = ""
    published_at: datetime | None = None
    content: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "original_title": self.original_title,
            "source": self.source,
            "source_url": self.source_url,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "content": self.content,
            "summary": self.summary,
            "tags": self.tags,
            "word_count": self.word_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_content(cls, content: Content) -> "Article":
        """从原始Content构建Article"""
        return cls(
            id=content.id,
            original_title=content.title,
            source=content.source_id,
            source_url=content.url,
            author=content.author,
            published_at=content.published_at,
            content=content.content,
            summary=content.summary,
            metadata=content.metadata,
        )