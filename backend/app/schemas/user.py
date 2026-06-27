"""用户相关 Pydantic 模型 — 使用 shared-models.auth 统一数据契约"""

from datetime import datetime

from pydantic import BaseModel

from shared_models.auth import UserRegisterRequest, UserLoginRequest, UserResponse


class TokenResponse(BaseModel):
    """登录成功返回 JWT 令牌"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
