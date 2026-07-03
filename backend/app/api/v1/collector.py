"""URL 采集 API 路由"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.article import Article
from app.schemas.article import CollectURLRequest, CollectResponse
from app.services.collect import collect_url, CollectResult

router = APIRouter(prefix="/collect", tags=["采集"])


@router.post("/url", response_model=CollectResponse, status_code=status.HTTP_200_OK)
async def collect_from_url(
    body: CollectURLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """从 URL 采集文章内容"""
    result = await collect_url(body.url)

    article = Article(
        user_id=current_user.get("sub"),
        source_type="url",
        source_content=result.content,
        source_url=result.source_url,
        word_count_original=result.word_count,
    )
    db.add(article)
    await db.flush()

    return CollectResponse(
        title=result.title,
        content=result.content,
        author=result.author,
        word_count=result.word_count,
        source_url=result.source_url,
    )
