"""
Tests for multi-platform publishing API.

Following TDD workflow:
1. Write tests first (this file)
2. Run tests (they should fail)
3. Write code to make tests pass
4. Run tests (they should pass)
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime

# Import the app and models
from web.server import app
from content_aggregator.models.publish import (
    PublishRequest,
    PublishResult,
    PublishTask,
)


class TestPublishAPI:
    """Test cases for POST /api/publish and GET /api/publish/{task_id}"""

    @pytest.fixture
    def client(self):
        """Create TestClient for FastAPI app."""
        return TestClient(app)

    @pytest.fixture
    def valid_publish_request(self):
        """Valid publish request payload."""
        return {
            "article_id": 123,
            "platforms": ["wechat", "zhihu"],
            "options": {}
        }

    @pytest.fixture
    def mock_publish_task(self):
        """Mock publish task response."""
        return {
            "task_id": "abc123",
            "article_id": 123,
            "platforms": ["wechat", "zhihu"],
            "status": "pending",
            "results": [],
            "created_at": datetime.now().isoformat()
        }

    # ===== Test Cases for POST /api/publish =====

    def test_post_publish_success(self, client, valid_publish_request, mock_publish_task):
        """Given valid publish request, when call POST /api/publish, then return task_id and status."""

        # Mock the publish task creation
        with patch("web.server.create_publish_task", return_value=mock_publish_task):
            response = client.post("/api/publish", json=valid_publish_request)

            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "pending"

    def test_post_publish_missing_article_id(self, client):
        """Given missing article_id, when call POST /api/publish, then return 422."""

        invalid_request = {
            "platforms": ["wechat"],
            "options": {}
        }

        response = client.post("/api/publish", json=invalid_request)

        # Assert 422 Unprocessable Entity
        assert response.status_code == 422

    def test_post_publish_missing_platforms(self, client):
        """Given missing platforms, when call POST /api/publish, then return 422."""

        invalid_request = {
            "article_id": 123,
            "options": {}
        }

        response = client.post("/api/publish", json=invalid_request)

        # Assert 422 Unprocessable Entity
        assert response.status_code == 422

    def test_post_publish_empty_platforms(self, client, valid_publish_request):
        """Given empty platforms list, when call POST /api/publish, then return 400."""

        invalid_request = valid_publish_request.copy()
        invalid_request["platforms"] = []

        response = client.post("/api/publish", json=invalid_request)

        # Assert 400 Bad Request
        assert response.status_code == 400
        assert "platforms" in response.json()["detail"].lower()

    def test_post_publish_invalid_platform(self, client, valid_publish_request):
        """Given invalid platform name, when call POST /api/publish, then return 400."""

        invalid_request = valid_publish_request.copy()
        invalid_request["platforms"] = ["invalid_platform"]

        response = client.post("/api/publish", json=invalid_request)

        # Assert 400 Bad Request
        assert response.status_code == 400
        assert "platform" in response.json()["detail"].lower()

    def test_post_publish_article_not_found(self, client, valid_publish_request):
        """Given article_id not exist, when call POST /api/publish, then return 404."""

        invalid_request = valid_publish_request.copy()
        invalid_request["article_id"] = 99999  # Non-existent article

        with patch("web.server.get_article_by_id", return_value=None):
            response = client.post("/api/publish", json=invalid_request)

            # Assert 404 Not Found
            assert response.status_code == 404
            assert "article" in response.json()["detail"].lower()

    # ===== Test Cases for GET /api/publish/{task_id} ======

    def test_get_publish_task_success(self, client, mock_publish_task):
        """Given valid task_id, when call GET /api/publish/{task_id}, then return task details."""

        task_id = "abc123"

        with patch("web.server.get_publish_task", return_value=mock_publish_task):
            response = client.get(f"/api/publish/{task_id}")

            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert data["task_id"] == task_id
            assert data["status"] == "pending"

    def test_get_publish_task_not_found(self, client):
        """Given task_id not exist, when call GET /api/publish/{task_id}, then return 404."""

        task_id = "nonexistent"

        with patch("web.server.get_publish_task", return_value=None):
            response = client.get(f"/api/publish/{task_id}")

            # Assert 404 Not Found
            assert response.status_code == 404
            assert "task" in response.json()["detail"].lower()

    def test_get_publish_task_running(self, client, mock_publish_task):
        """Given task is running, when call GET /api/publish/{task_id}, then return status=running and partial results."""

        task_id = "abc123"
        mock_publish_task["status"] = "running"
        mock_publish_task["results"] = [
            {"platform": "wechat", "status": "success", "url": "https://..."},
            {"platform": "zhihu", "status": "running"}
        ]

        with patch("web.server.get_publish_task", return_value=mock_publish_task):
            response = client.get(f"/api/publish/{task_id}")

            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert len(data["results"]) == 2
            assert data["results"][0]["status"] == "success"
            assert data["results"][1]["status"] == "running"

    def test_get_publish_task_completed(self, client, mock_publish_task):
        """Given task is completed, when call GET /api/publish/{task_id}, then return status=completed and all results."""

        task_id = "abc123"
        mock_publish_task["status"] = "completed"
        mock_publish_task["results"] = [
            {"platform": "wechat", "status": "success", "url": "https://..."},
            {"platform": "zhihu", "status": "success", "url": "https://..."}
        ]

        with patch("web.server.get_publish_task", return_value=mock_publish_task):
            response = client.get(f"/api/publish/{task_id}")

            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert len(data["results"]) == 2
            assert all(r["status"] == "success" for r in data["results"])

    def test_get_publish_task_failed(self, client, mock_publish_task):
        """Given task is failed, when call GET /api/publish/{task_id}, then return status=failed and error message."""

        task_id = "abc123"
        mock_publish_task["status"] = "failed"
        mock_publish_task["results"] = [
            {"platform": "wechat", "status": "failed", "message": "API Key not configured"}
        ]

        with patch("web.server.get_publish_task", return_value=mock_publish_task):
            response = client.get(f"/api/publish/{task_id}")

            # Assert response
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert "error" in data or "message" in data["results"][0]

    # ===== Test Cases for Input Validation =====

    def test_post_publish_invalid_json(self, client):
        """Given invalid JSON, when call POST /api/publish, then return 422."""

        response = client.post(
            "/api/publish",
            data="{invalid json}",
            headers={"Content-Type": "application/json"}
        )

        # Assert 422 Unprocessable Entity
        assert response.status_code == 422

    def test_post_publish_unsupported_media_type(self, client, valid_publish_request):
        """Given unsupported media type, when call POST /api/publish, then return 415."""

        response = client.post(
            "/api/publish",
            data="article_id=123&platforms=wechat",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        # Assert 415 Unsupported Media Type (or 422 if FastAPI auto-parses)
        assert response.status_code in [415, 422]

    # ===== Test Cases for Concurrency =====

    @pytest.mark.asyncio
    async def test_post_publish_concurrent_requests(self, client, valid_publish_request):
        """Given multiple concurrent requests, when call POST /api/publish, then all tasks created successfully."""
        
        import asyncio
        from functools import partial
        
        # Mock task creation
        with patch("web.server.create_publish_task") as mock_create:
            mock_create.side_effect = [
                {"task_id": f"task_{i}", "status": "pending"}
                for i in range(5)
            ]
            
            # Send 5 concurrent requests
            tasks = [
                asyncio.get_event_loop().run_in_executor(
                    None,
                    partial(client.post, "/api/publish", json=valid_publish_request)
                )
                for _ in range(5)
            ]
            
            responses = await asyncio.gather(*tasks)
            
            # Assert all succeeded
            assert all(r.status_code == 200 for r in responses)
            assert mock_create.call_count == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
