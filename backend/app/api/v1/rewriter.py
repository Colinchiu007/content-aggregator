"""AI 改写 API 路由"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.article import Article
from app.schemas.article import RewriteRequest, RewriteResponse
from app.services.rewrite import rewrite_content

router = APIRouter(prefix="/rewrite", tags=["改写"])


@router.post("/", response_model=RewriteResponse, status_code=status.HTTP_200_OK)
async def rewrite(
    body: RewriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """对指定文章进行 AI 改写"""
    user_id = current_user.get("sub")
    result = await db.execute(
        select(Article).where(
            Article.id == body.article_id,
            Article.user_id == user_id,
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    rewrite_result = await rewrite_content(
        content=article.source_content or "",
        style=body.style,
        length=body.length,
        seo_optimize=body.seo_optimize,
    )

    article.rewrite_style = body.style
    article.rewrite_length = body.length
    article.result_content = rewrite_result.result_content
    article.word_count_result = rewrite_result.word_count
    await db.flush()

    return RewriteResponse(
        article_id=body.article_id,
        result_content=rewrite_result.result_content,
        word_count=rewrite_result.word_count,
        style=body.style,
    )
