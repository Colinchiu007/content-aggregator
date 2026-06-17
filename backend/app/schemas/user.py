"""用户相关 Pydantic 模型 — 请求/响应数据结构"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ──────────────────────────────────────────────
# 请求体
# ──────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, max_length=128, description="密码")


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


# ──────────────────────────────────────────────
# 响应体
# ──────────────────────────────────────────────

class UserResponse(BaseModel):
    """用户基础信息"""
    id: UUID
    username: str
    email: str
    subscription_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录成功返回 JWT 令牌"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
