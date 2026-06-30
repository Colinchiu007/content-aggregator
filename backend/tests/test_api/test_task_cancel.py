"""Task API 测试 — DELETE /api/v1/tasks/{task_id}"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestCancelTask:
    """DELETE /api/v1/tasks/{task_id} — 取消任务"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, async_client, monkeypatch):
        client, mock_db = async_client
        self.client = client
        self.mock_db = mock_db

    @pytest.mark.asyncio
    async def test_cancel_task_success(self):
        """取消 pending 任务应返回 200"""
        task_id = "test-task-id-001"

        # Mock task found with pending status
        mock_task = MagicMock()
        mock_task.id = task_id
        mock_task.status = "pending"
        mock_task.celery_task_id = None
        self.mock_db.get = AsyncMock(return_value=mock_task)

        resp = await self.client.delete(f"/api/v1/tasks/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self):
        """不存在的任务应返回 404"""
        self.mock_db.get = AsyncMock(return_value=None)

        resp = await self.client.delete("/api/v1/tasks/nonexistent-task")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self):
        """已完成的任务应返回 400"""
        mock_task = MagicMock()
        mock_task.status = "completed"
        mock_task.celery_task_id = None
        self.mock_db.get = AsyncMock(return_value=mock_task)

        resp = await self.client.delete("/api/v1/tasks/completed-task")
        assert resp.status_code == 400
