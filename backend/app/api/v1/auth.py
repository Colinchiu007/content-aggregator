"""Auth API route — 使用 shared-models UserResponse."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db

router = APIRouter(prefix="/auth", tags=["认证"])


# ── Password Reset Schemas ──────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)


# ── Existing /me endpoint ────────────────────────────────────────────────


@router.get("/me", response_model=dict)
async def get_me(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """获取当前登录用户信息（需携带 Bearer Token）

    Phase C: 纯 JWT 验签，orchestrator 签发。
    """
    from uuid import UUID
    return {
        "id": UUID(current_user.get("sub")),
        "username": current_user.get("sub"),
        "email": current_user.get("email", ""),
        "subscription_type": current_user.get("subscription_type", "free"),
    }


# ── Password Reset Endpoints ────────────────────────────────────────────


@router.post("/forgot-password")
async def forgot_password_endpoint(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """请求密码重置邮件。

    始终返回成功以防止邮箱枚举攻击。
    """
    from app.services.auth_service import forgot_password

    return await forgot_password(email=body.email, db=db)


@router.post("/reset-password")
async def reset_password_endpoint(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """使用重置令牌设置新密码。"""
    from app.services.auth_service import reset_password

    try:
        return await reset_password(token=body.token, new_password=body.new_password, db=db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
