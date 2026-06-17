"""文章管理 API 路由 — CRUD 操作"""

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.article import Article
from app.models.user import User
from app.schemas.article import ArticleResponse, ArticleListItem

router = APIRouter(prefix="/articles", tags=["文章"])


@router.get("/", response_model=dict)
async def list_articles(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取当前用户的文章列表（分页）

    - 按创建时间倒序排列
    - 支持分页参数 page / page_size
    """
    # 总数
    count_result = await db.execute(
        select(func.count(Article.id)).where(Article.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Article)
        .where(Article.user_id == current_user.id)
        .order_by(Article.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    articles = result.scalars().all()

    return {
        "items": [ArticleListItem.model_validate(a) for a in articles],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Article:
    """获取单篇文章详情"""
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在",
        )

    return article


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_article(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除文章（同时删除关联的发布日志）"""
    result = await db.execute(
        select(Article).where(
            Article.id == article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文章不存在",
        )

    await db.delete(article)
    await db.flush()
