"""JWT 令牌创建与验证 — 使用 shared-models JWTAuthManager"""

from shared_models.auth import JWTAuthManager
from app.config import get_settings

settings = get_settings()

# JWTAuthManager 实例（统一 JWT + 密码工具）
auth_manager = JWTAuthManager(
    secret_key=settings.SECRET_KEY,
    algorithm="HS256",
    access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
)

# 直接暴露静态方法（与旧签名完全兼容）
verify_password = JWTAuthManager.verify_password
hash_password = JWTAuthManager.hash_password


def create_access_token(subject: str, expires_delta=None) -> str:
    """创建 JWT 访问令牌 — 兼容旧签名"""
    return auth_manager.create_access_token(
        {"sub": str(subject)},
        expires_delta=expires_delta,
    )


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT 访问令牌 — 兼容旧签名"""
    return auth_manager.decode_token(token)
