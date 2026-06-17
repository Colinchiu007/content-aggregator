"""v1 API 路由聚合器 — 将所有子路由挂载到统一前缀"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.articles import router as articles_router
from app.api.v1.collector import router as collector_router
from app.api.v1.rewriter import router as rewriter_router
from app.api.v1.publisher import router as publisher_router

api_v1_router = APIRouter(prefix="/api/v1")

# 挂载子路由
api_v1_router.include_router(auth_router)
api_v1_router.include_router(articles_router)
api_v1_router.include_router(collector_router)
api_v1_router.include_router(rewriter_router)
api_v1_router.include_router(publisher_router)


# ──────────────────────────────────────────────
# 健康检查端点
# ──────────────────────────────────────────────

@api_v1_router.get("/health", tags=["系统"])
async def health_check() -> dict:
    """健康检查 — 确认服务正在运行"""
    return {
        "status": "healthy",
        "service": "HotRewrite v2",
        "version": "0.1.0",
    }
