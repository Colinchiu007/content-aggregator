"""竞品监控 Pydantic 模型 — 请求/响应数据结构"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 监控源
# ──────────────────────────────────────────────

class MonitorSourceCreate(BaseModel):
    """创建监控源请求"""
    name: str = Field(..., max_length=200, description="监控源名称")
    source_type: str = Field(..., description="wechat / zhihu / url")
    identifier: str = Field(..., description="公众号ID / 知乎UID / URL")
    schedule_cron: str | None = Field(None, description="自定义采集频率 (cron)")


class MonitorSourceUpdate(BaseModel):
    """更新监控源请求"""
    name: str | None = Field(None, max_length=200)
    source_type: str | None = Field(None)
    identifier: str | None = Field(None)
    schedule_cron: str | None = Field(None)
    is_active: bool | None = Field(None)


class MonitorSourceResponse(BaseModel):
    """监控源响应"""
    id: UUID
    user_id: UUID
    name: str
    source_type: str
    identifier: str
    schedule_cron: str | None
    is_active: bool
    last_collected_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# 监控文章
# ──────────────────────────────────────────────

class MonitorArticleResponse(BaseModel):
    """监控文章响应"""
    id: UUID
    source_id: UUID
    title: str
    url: str
    summary: str | None
    cover_url: str | None
    author: str | None
    published_at: datetime | None
    is_read: bool
    collected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class MonitorArticleListParams(BaseModel):
    """监控文章列表参数"""
    source_id: UUID | None = Field(None, description="按监控源筛选")
    is_read: bool | None = Field(None, description="按已读状态筛选")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
