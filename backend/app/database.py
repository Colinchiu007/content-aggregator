"""数据库引擎与会话管理 — async SQLAlchemy 2.0"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 动态构建引擎参数 — SQLite 不支持 pool_size/max_overflow
_engine_kwargs: dict = {
    "echo": settings.DEBUG,
}
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True

# 异步引擎（echo 仅在 DEBUG 模式下开启，方便开发时查看 SQL）
engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs,
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类 — 所有 ORM 模型继承此基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入 — 获取数据库会话

    Yields:
        AsyncSession: 数据库会话实例，请求结束后自动关闭
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
