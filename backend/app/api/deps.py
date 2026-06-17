"""FastAPI 依赖注入 — 数据库会话、当前用户"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import decode_access_token

# HTTP Bearer 认证方案
security_scheme = HTTPBearer()


async def get_db() -> AsyncSession:  # type: ignore[misc]
    """获取数据库会话（每个请求独立的会话）"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT 令牌中获取当前登录用户

    Args:
        credentials: HTTP Bearer 认证凭证
        db: 数据库会话

    Returns:
        User: 当前登录的用户模型实例

    Raises:
        HTTPException 401: 令牌无效、过期或用户不存在
    """
    token = credentials.credentials

    # 解码 JWT 令牌
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
            )
        user_id = UUID(user_id_str)
    except (JWTError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证令牌无效或已过期: {e}",
        ) from e

    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被删除",
        )

    return user
