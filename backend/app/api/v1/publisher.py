"""多平台发布 API 路由（Phase A: JWT payload dict）"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.schemas.article import PublishRequest, PublishTaskResponse
from app.schemas.publish import PublishStatusResponse, PublishLogItem
from app.services.publisher import create_publish_tasks, get_publish_status

router = APIRouter(prefix="/publish", tags=["发布"])


@router.post("/", response_model=PublishTaskResponse, status_code=status.HTTP_201_CREATED)
async def publish(
    body: PublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """发布文章到指定平台

    - 支持多平台同时发布
    - 返回发布任务 ID（= article_id），可用于查询状态
    """
    result = await create_publish_tasks(
        article_id=body.article_id,
        user_id=current_user.get("sub"),
        platforms=body.platforms,
    )
    return PublishTaskResponse(**result)


@router.get("/status/{task_id}", response_model=PublishStatusResponse)
async def publish_status(
    task_id: UUID,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """查询发布任务状态

    - task_id 即为 article_id
    - 返回各平台的发布结果
    """
    result = await get_publish_status(article_id=task_id)
    return PublishStatusResponse(
        task_id=result["task_id"],
        logs=[PublishLogItem(**log) for log in result["logs"]],
    )
