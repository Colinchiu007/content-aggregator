"""认证 API 测试 — 密码重置端点"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import MockScalarResult


class TestForgotPassword:
    """POST /api/v1/auth/forgot-password"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_forgot_password_always_returns_success(self):
        """即使邮箱不存在也返回 200（防枚举）"""
        self.mock_db.execute = AsyncMock(
            return_value=MockScalarResult(scalars_list=[], scalars_first=None)
        )
        resp = await self.client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_forgot_password_invalid_email(self):
        """无效邮箱格式应返回 422"""
        resp = await self.client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_forgot_password_empty_email(self):
        """缺少 email 字段应返回 422"""
        resp = await self.client.post(
            "/api/v1/auth/forgot-password",
            json={},
        )
        assert resp.status_code == 422


class TestResetPassword:
    """POST /api/v1/auth/reset-password"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_reset_password_success(self):
        """有效 token 应返回 200"""
        from app.core.security import create_access_token

        user_id = str(uuid.uuid4())
        token = create_access_token(subject=user_id)

        # Mock db.get returns the user
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.password_hash = "old_hash"
        self.mock_db.get = AsyncMock(return_value=mock_user)
        self.mock_db.flush = AsyncMock()

        resp = await self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "new-secure-pwd-123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self):
        """无效 token 应返回 400"""
        resp = await self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid.jwt.token", "new_password": "new-secure-pwd-123"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_password_short_password(self):
        """密码过短应返回 422"""
        resp = await self.client.post(
            "/api/v1/auth/reset-password",
            json={"token": "some.valid.jwt", "new_password": "ab"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_reset_password_empty_body(self):
        """空请求体应返回 422"""
        resp = await self.client.post(
            "/api/v1/auth/reset-password",
            json={},
        )
        assert resp.status_code == 422
