"""AI 改写 API 路由"""

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.article import Article
from app.models.user import User
from app.schemas.article import RewriteRequest, RewriteResponse
from app.services.rewriter import rewrite_article

router = APIRouter(prefix="/rewrite", tags=["改写"])


@router.post("/", response_model=RewriteResponse, status_code=status.HTTP_200_OK)
async def rewrite(
    body: RewriteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """对指定文章进行 AI 改写

    - 支持 4 种风格：轻松易懂 / 正式严谨 / 吸引眼球 / 深度分析
    - 支持 3 种长度策略：keep / compress / expand
    - 可选 SEO 优化
    - 改写结果写入文章记录
    """
    # 检查文章所有权
    result = await db.execute(
        select(Article).where(
            Article.id == body.article_id,
            Article.user_id == current_user.id,
        )
    )
    article = result.scalar_one_or_none()
    if not article:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="文章不存在")

    # 调用改写服务
    rewrite_result = await rewrite_article(
        article_id=body.article_id,
        style=body.style,
        length=body.length,
        seo_optimize=body.seo_optimize,
    )

    # 保存改写结果到数据库
    article.rewrite_style = body.style
    article.rewrite_length = body.length
    article.result_content = rewrite_result["result_content"]
    article.word_count_result = rewrite_result["word_count"]
    await db.flush()

    return RewriteResponse(
        article_id=body.article_id,
        result_content=rewrite_result["result_content"],
        word_count=rewrite_result["word_count"],
        style=body.style,
    )
