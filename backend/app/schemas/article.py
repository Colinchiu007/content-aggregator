"""文章相关 Pydantic 模型 — 请求/响应数据结构"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# 请求体
# ──────────────────────────────────────────────

class ArticleCreateRequest(BaseModel):
    """创建文章记录请求（采集后保存原始内容）"""
    source_type: str = Field(..., description="来源类型: url / text / file")
    source_content: str | None = Field(None, description="原始文章内容")
    source_url: str | None = Field(None, description="来源 URL")
    word_count_original: int | None = Field(None, description="原文词数")


class CollectURLRequest(BaseModel):
    """URL 采集请求"""
    url: str = Field(..., description="要采集的文章 URL")


class RewriteRequest(BaseModel):
    """AI 改写请求"""
    article_id: UUID = Field(..., description="要改写的文章 ID")
    style: str = Field(..., description="改写风格: 轻松易懂 / 正式严谨 / 吸引眼球 / 深度分析")
    length: str = Field(default="keep", description="长度策略: keep / compress / expand")
    seo_optimize: bool = Field(default=False, description="是否启用 SEO 优化")


class PublishRequest(BaseModel):
    """发布请求"""
    article_id: UUID = Field(..., description="要发布的文章 ID")
    platforms: list[str] = Field(..., min_length=1, description="目标平台列表: wechat / zhihu / toutiao")


# ──────────────────────────────────────────────
# 响应体
# ──────────────────────────────────────────────

class ArticleResponse(BaseModel):
    """文章完整响应（含改写结果）"""
    id: UUID
    user_id: UUID
    source_type: str
    source_content: str | None
    source_url: str | None
    rewrite_style: str | None
    rewrite_length: str | None
    result_content: str | None
    word_count_original: int | None
    word_count_result: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleListItem(BaseModel):
    """文章列表项（摘要，不含全文）"""
    id: UUID
    source_type: str
    source_url: str | None
    rewrite_style: str | None
    word_count_original: int | None
    word_count_result: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CollectResponse(BaseModel):
    """URL 采集结果"""
    title: str
    content: str
    author: str | None = None
    word_count: int
    source_url: str


class RewriteResponse(BaseModel):
    """AI 改写结果"""
    article_id: UUID
    result_content: str
    word_count: int
    style: str


class PublishTaskResponse(BaseModel):
    """发布任务创建结果"""
    task_id: str = Field(..., description="发布批次的追踪 ID（article_id）")
    platforms: list[str]
    message: str = "发布任务已创建"


class PublishStatusResponse(BaseModel):
    """发布状态查询结果"""
    task_id: UUID
    logs: list["PublishLogItem"]


class PublishLogItem(BaseModel):
    """单条发布日志"""
    id: UUID
    platform: str
    status: str  # pending / success / failed
    error_message: str | None
    published_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
