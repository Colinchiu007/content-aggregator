"""URL 采集 API 路由"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.article import Article
from app.models.user import User
from app.schemas.article import CollectURLRequest, CollectResponse
from app.services.collector import collect_url

router = APIRouter(prefix="/collect", tags=["采集"])


@router.post("/url", response_model=CollectResponse, status_code=status.HTTP_200_OK)
async def collect_from_url(
    body: CollectURLRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """从 URL 采集文章内容

    - 使用 httpx + trafilatura 提取正文
    - 采集结果自动保存到用户文章列表
    - 返回标题、内容、作者和字数统计
    """
    # 1. 采集内容
    result = await collect_url(body.url)

    # 2. 保存到数据库
    article = Article(
        user_id=current_user.id,
        source_type="url",
        source_content=result["content"],
        source_url=result["source_url"],
        word_count_original=result["word_count"],
    )
    db.add(article)
    await db.flush()

    return CollectResponse(
        title=result["title"],
        content=result["content"],
        author=result["author"],
        word_count=result["word_count"],
        source_url=result["source_url"],
    )
