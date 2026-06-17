"""
Models for multi-platform publishing.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class PublishRequest(BaseModel):
    """Request model for POST /api/publish."""

    article_id: int = Field(..., description="ID of the article to publish")
    platforms: List[str] = Field(
        ...,
        description="List of platforms to publish to (wechat, zhihu, csdn, juejin)"
    )
    options: Dict = Field(default={}, description="Additional options for publishing")


class PublishResult(BaseModel):
    """Result model for a single platform publish attempt."""

    platform: str = Field(..., description="Platform name")
    status: str = Field(
        ...,
        pattern="^(success|failed)$",
        description="Publish status: success or failed"
    )
    message: str = Field(default="", description="Error message if failed")
    url: Optional[str] = Field(default=None, description="Published article URL if success")


class PublishTask(BaseModel):
    """Task model for tracking publish progress."""

    task_id: str = Field(..., description="Unique task ID")
    article_id: int = Field(..., description="Article ID being published")
    platforms: List[str] = Field(..., description="List of platforms")
    status: str = Field(
        ...,
        pattern="^(pending|running|completed|failed)$",
        description="Task status"
    )
    results: List[PublishResult] = Field(
        default=[],
        description="Publish results for each platform"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Task creation time"
    )
