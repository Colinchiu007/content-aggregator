"""数据库引擎与会话管理 — async SQLAlchemy 2.0"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# 异步引擎（echo 仅在 DEBUG 模式下开启，方便开发时查看 SQL）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
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


async def get_db() -> AsyncSession:  # type: ignore[misc]
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
