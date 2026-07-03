"""FastAPI 应用工厂 — 应用入口点"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.v1.router import api_v1_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理 — 启动/关闭时执行的逻辑"""
    # 启动时
    yield
    # 关闭时
    # 目前无需额外清理


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例

    Returns:
        FastAPI: 配置完成的应用实例，包含：
          - CORS 中间件（允许前端跨域访问）
          - v1 API 路由
          - 全局异常处理
          - 自动生成的 OpenAPI 文档
    """
    app = FastAPI(
        title="HotRewrite API",
        description="热文改写一站式平台 — URL 采集 → AI 改写 → 多平台发布",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS 中间件 — 允许前端跨域请求
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册 API 路由
    app.include_router(api_v1_router)

    return app


# 模块级应用实例（供 uvicorn 直接引用）
app = create_app()
