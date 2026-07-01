"""Test infrastructure — conftest.py"""

import os as _os
_os.environ.setdefault("SECRET_KEY", "test-secret-key-for-content-aggregator-tdd-2026")
_os.environ.setdefault("PO_SECRET_KEY", "test-secret-key-for-content-aggregator-tdd-2026")
_os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
_os.environ.setdefault("OPENAI_BASE_URL", "https://api.test.local/v1")
_os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")
_os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_cache.db")

import asyncio
import uuid as _uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, hash_password


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def make_token():
    def _make(user_id: str | None = None) -> str:
        return create_access_token(subject=user_id or str(_uuid.uuid4()))
    return _make


@pytest.fixture
def sample_user_id() -> str:
    return "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


@pytest.fixture
def sample_user_token(make_token, sample_user_id) -> str:
    return make_token(sample_user_id)


# ---------------------------------------------------------------------------
# Build a mock result object that chain-calls correctly
# ---------------------------------------------------------------------------
class MockScalarResult:
    """Mock for SQLAlchemy Result.scalar / .scalar_one_or_none / .scalars().all()"""
    def __init__(self, scalar_val=None, scalar_one=None, scalars_list=None, scalars_first=None):
        self._scalar_val = scalar_val
        self._scalar_one = scalar_one
        self._scalars_list = scalars_list or []
        self._scalars_first = scalars_first

    def scalar(self):
        return self._scalar_val

    def scalar_one_or_none(self):
        return self._scalar_one

    def scalars(self):
        class _Scalars:
            def all(_):
                return self._scalars_list
            def first(_):
                return self._scalars_first
        return _Scalars()


# ---------------------------------------------------------------------------
# Mocked async_client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def async_client(sample_user_id, make_token, monkeypatch) -> AsyncGenerator[tuple, None]:
    """Create async HTTPX client with fully mocked DB session."""
    from app.main import create_app
    from sqlalchemy.ext.asyncio import AsyncSession

    app = create_app()

    # Create a mock async session with proper async execute
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.delete = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    # execute must be awaitable and return a result
    mock_session.execute = AsyncMock(
        return_value=MockScalarResult(scalar_val=0, scalars_list=[])
    )

    # Mock context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session_factory = MagicMock(return_value=mock_cm)

    # Patch BOTH locations
    monkeypatch.setattr("app.database.AsyncSessionLocal", mock_session_factory)
    monkeypatch.setattr("app.api.deps.AsyncSessionLocal", mock_session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {make_token(sample_user_id)}"
        yield client, mock_session


# ---------------------------------------------------------------------------
# Real SQLite session for service-layer tests
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_db():
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from app.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
def mock_celery_app():
    mock_task = MagicMock()
    mock_task.delay = MagicMock(return_value=MagicMock(id="mock-task-id"))
    mock_task.apply_async = MagicMock(return_value=MagicMock(id="mock-task-id"))

    mock_app = MagicMock()
    mock_app.task = MagicMock(return_value=mock_task)
    mock_app.control = MagicMock()
    return mock_app, mock_task


@pytest.fixture
def mock_httpx_post(monkeypatch):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={
        "choices": [{"message": {"content": "# Rewritten\n\nMocked content."}}]
    })

    mock_client_class = MagicMock()
    mock_client_instance = AsyncMock()
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
    mock_client_instance.post = AsyncMock(return_value=mock_response)
    mock_client_class.return_value = mock_client_instance

    monkeypatch.setattr("httpx.AsyncClient", mock_client_class)
    return mock_client_instance, mock_response
