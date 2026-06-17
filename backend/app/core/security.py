"""JWT 令牌创建与验证"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# 密码哈希上下文（bcrypt）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """对明文密码进行哈希处理"""
    return pwd_context.hash(password)


def create_access_token(subject: str | UUID, expires_delta: timedelta | None = None) -> str:
    """创建 JWT 访问令牌

    Args:
        subject: 令牌主体（通常是用户 ID 或用户名）
        expires_delta: 过期时间增量，默认使用配置中的值

    Returns:
        str: 编码后的 JWT 令牌字符串
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """解码并验证 JWT 访问令牌

    Args:
        token: JWT 令牌字符串

    Returns:
        dict: 令牌负载

    Raises:
        JWTError: 令牌无效或已过期
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
