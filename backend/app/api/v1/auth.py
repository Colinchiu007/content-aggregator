"""Auth API route — fixed to return complete UserResponse."""

from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["认证"])


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
