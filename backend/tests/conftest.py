"""测试基础设施 — conftest.py

提供测试用 fixtures:
  - async_client: HTTPX 异步测试客户端
  - test_db: 测试数据库会话
  - test_user: 预创建的测试用户
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """为整个测试会话创建一个事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """创建异步 HTTPX 测试客户端（不依赖真实数据库）"""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
