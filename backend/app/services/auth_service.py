"""Authentication service — forgot password, reset password, email sending.

This module handles password reset flows:
- Generates JWT-based reset tokens (1h expiry)
- Sends reset emails (or logs in dev mode)
- Validates tokens and updates passwords
"""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import (
    auth_manager,
    create_access_token,
    decode_access_token,
    hash_password,
)
from app.models.user import User

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────
RESET_TOKEN_EXPIRE_HOURS = 1


async def send_reset_email(email: str, reset_token: str, username: str) -> bool:
    """Send password reset email to the user.

    Currently logs the reset link to console (dev mode).
    In production, integrate with SMTP / email service API.

    Args:
        email: Recipient email address
        reset_token: JWT reset token
        username: User's display name

    Returns:
        bool: True if email was sent successfully
    """
    # TODO: Replace with real SMTP / email service integration
    reset_link = f"/auth/reset-password?token={reset_token}"
    logger.info(
        "🔗 密码重置链接（开发模式）: %s\n"
        "  用户: %s, 邮箱: %s, 有效期: %d 小时",
        reset_link, username, email, RESET_TOKEN_EXPIRE_HOURS,
    )
    return True


async def forgot_password(email: str, db: AsyncSession) -> dict:
    """Initiate password reset flow for the given email.

    Always returns success to prevent email enumeration attacks.
    If the email exists, sends a reset link.

    Args:
        email: Registered email address
        db: Database session

    Returns:
        dict: Success message
    """
    # Find user by email (without revealing if user exists)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()

    if user is not None:
        reset_token = create_access_token(
            subject=str(user.id),
            expires_delta=timedelta(hours=RESET_TOKEN_EXPIRE_HOURS),
        )
        await send_reset_email(
            email=email,
            reset_token=reset_token,
            username=user.username,
        )

    return {"message": "密码重置邮件已发送"}


async def reset_password(token: str, new_password: str, db: AsyncSession) -> dict:
    """Reset user password using a valid reset token.

    Args:
        token: JWT reset token
        new_password: New password (min 6 chars)
        db: Database session

    Returns:
        dict: Success message

    Raises:
        ValueError: If token is invalid, expired, or user not found
    """
    # Validate token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise ValueError("重置链接已过期或无效")
    except Exception as e:
        raise ValueError("重置链接已过期或无效") from e

    # Find user
    user = await db.get(User, user_id)
    if user is None:
        raise ValueError("重置链接已过期或无效")

    # Update password
    user.password_hash = hash_password(new_password)
    await db.flush()

    logger.info("密码重置成功: user_id=%s", user_id)
    return {"message": "密码重置成功"}
