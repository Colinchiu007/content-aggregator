"""热榜发现 API 路由 — TrendScope 代理层

通过 HTTP 调用 TrendScope 的 /api/v1/trending 端点，返回聚合热榜数据。
附带「一键改写」端点：选取热榜话题 → 采集内容 → 创建文章 → 返回 article_id。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.article import Article
from app.schemas.article import CollectResponse
from app.config import get_settings


import httpx

router = APIRouter(prefix="/trending", tags=["热榜发现"])


def _trendscope_client() -> httpx.AsyncClient:
    """创建指向 TrendScope API 的 HTTP 客户端"""
    settings = get_settings()
    base_url = settings.TRENDSCOPE_API_URL.rstrip("/")
    return httpx.AsyncClient(base_url=base_url, timeout=15.0)


@router.get("/platforms")
async def list_platforms():
    """获取 TrendScope 支持的平台列表"""
    async with _trendscope_client() as client:
        resp = await client.get("/api/v1/trending/platforms")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="热榜服务不可用")
    data = resp.json()
    return {"code": 0, "data": data.get("data", {})}


@router.get("")
async def get_aggregated_trending(
    platforms: str = Query(None, description="逗号分隔的平台代码"),
    category: str = Query("all"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取聚合热榜数据（代理 TrendScope）"""
    params = {"category": category, "page": page, "page_size": page_size}
    if platforms:
        params["platforms"] = platforms

    async with _trendscope_client() as client:
        resp = await client.get("/api/v1/trending", params=params)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="热榜服务不可用")
    return resp.json()


@router.get("/{platform}")
async def get_platform_trending(
    platform: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """获取指定平台的热榜数据（代理 TrendScope）"""
    params = {"page": page, "page_size": page_size}

    async with _trendscope_client() as client:
        resp = await client.get(f"/api/v1/trending/{platform}", params=params)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="热榜服务不可用")
    return resp.json()


@router.post("/rewrite", status_code=status.HTTP_200_OK)
async def rewrite_trending_topic(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """「一键改写」— 从热榜话题采集内容并创建文章

    请求体：
    {
        "topic_id": int,          // TrendScope 话题 ID
        "topic_url": str,         // 话题链接（用于内容采集）
        "title": str,             // 话题标题
        "platform_code": str      // 平台代码
    }
    """
    topic_id = body.get("topic_id")
    topic_url = body.get("topic_url", "")
    title = body.get("title", "")
    platform_code = body.get("platform_code", "")

    if not topic_id and not topic_url:
        raise HTTPException(status_code=422, detail="需要 topic_id 或 topic_url")

    # 1. 先尝试从 TrendScope 获取文章详情
    content_text = ""
    source_url = topic_url or ""

    if topic_id:
        async with _trendscope_client() as client:
            resp = await client.get(f"/api/v1/articles/{topic_id}")
            if resp.status_code == 200:
                article_data = resp.json().get("data", {})
                content_text = article_data.get("summary") or article_data.get("content_text", "")
                source_url = article_data.get("source_url") or source_url

    # 2. 如果 TrendScope 没有内容，尝试通过 topic_url 采集
    if not content_text and source_url:
        try:
            from app.services.collect import collect_url
            collect_result = await collect_url(source_url)
            content_text = collect_result.content
        except Exception:
            # 采集失败时，至少保留标题作为内容
            content_text = title

    # 3. 如果仍然没有内容，就用标题作为内容
    if not content_text:
        content_text = title

    # 4. 创建文章
    article = Article(
        user_id=current_user.get("sub"),
        source_type="url",
        source_content=content_text,
        source_url=source_url,
        word_count_original=len(content_text),
    )
    db.add(article)
    await db.flush()

    return {
        "code": 0,
        "data": {
            "article_id": article.id,
            "title": title,
            "word_count": len(content_text),
            "source_url": source_url,
        },
    }
