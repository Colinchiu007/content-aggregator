"""FastAPI 依赖注入 — 数据库会话、当前用户（Phase A: 纯 JWT 验签，不查 DB）"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
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
) -> dict:
    """从 JWT 令牌解析当前用户（Phase A: 纯验签，不查 DB）

    Args:
        credentials: HTTP Bearer 认证凭证

    Returns:
        dict: JWT payload {sub, exp, iat}，其中 sub 为 user UUID 字符串

    Raises:
        HTTPException 401: 令牌无效或过期
    """
    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
            )
        return payload
    except (ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证令牌无效或已过期: {e}",
        ) from e
