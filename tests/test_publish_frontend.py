"""
Tests for Task 2.1 - 前端多平台发布 UI.

TDD workflow: write tests first → run (should fail) → implement → run (should pass).
Tests verify compose.html has publish UI elements and JS functions.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create FastAPI test client."""
    from web.server import app
    return TestClient(app)


class TestPublishFrontend:
    """Test cases for Task 2.1 - 前端多平台发布 UI"""

    # ===== 2.1.1 发布弹窗 UI =====

    def test_compose_page_returns_200(self, client):
        """Given any request, when GET /compose, then return 200."""
        resp = client.get("/compose")
        assert resp.status_code == 200

    def test_compose_page_has_publish_section(self, client):
        """Given compose page, then it should contain publish action elements after rewrite result."""
        resp = client.get("/compose")
        html = resp.text
        # 一键发布区域应出现在改写结果之后
        assert '一键发布' in html or 'publish-section' in html or 'publish-btn' in html

    def test_compose_page_has_platform_checkboxes(self, client):
        """Given compose page, then it should have platform checkboxes for wechat and zhihu."""
        resp = client.get("/compose")
        html = resp.text.lower()
        # 至少应该包含微信和知乎平台选项
        has_wechat = 'wechat' in html or '微信' in html
        has_zhihu = 'zhihu' in html or '知乎' in html
        assert has_wechat, "缺少微信发布选项"
        assert has_zhihu, "缺少知乎发布选项"

    def test_publish_section_is_hidden_initially(self, client):
        """Given compose page, then publish section should be hidden until rewrite is done."""
        resp = client.get("/compose")
        html = resp.text
        # 发布区域默认为 display:none
        assert 'publish-section' not in html or 'display:none' in html.lower() or 'style="display:none"' in html.lower()

    # ===== 2.1.2 发布 JS 函数 =====

    def test_publish_js_functions_exist(self, client):
        """Given compose page, then it should include publish-related JS functions."""
        resp = client.get("/compose")
        html = resp.text
        # 必须有的 JS 函数
        js_functions = ['handlePublish', 'pollPublishTask']
        for func in js_functions:
            assert func in html, f"缺少 JS 函数: {func}"

    def test_publish_js_fetches_article_id(self, client):
        """Given compose page JS, then handlePublish should read article_id from the DOM."""
        resp = client.get("/compose")
        html = resp.text
        # handlePublish 应读取改写结果的 article_id
        assert 'articleId' in html or 'article_id' in html

    def test_publish_calls_api_endpoint(self, client):
        """Given compose page JS, then handlePublish should POST /api/publish."""
        resp = client.get("/compose")
        html = resp.text
        # 应调用 /api/publish 接口
        assert '/api/publish' in html

    def test_publish_polls_task_progress(self, client):
        """Given compose page JS, then pollPublishTask should GET /api/publish/{task_id}."""
        resp = client.get("/compose")
        html = resp.text
        # 应轮询 /api/publish/{task_id}
        assert 'api/publish/' in html

    # ===== 2.1.3 发布进度显示 =====

    def test_publish_has_platform_progress_display(self, client):
        """Given compose page, then it should show per-platform progress."""
        resp = client.get("/compose")
        html = resp.text
        # 应有显示各平台发布进度的地方
        assert 'progress' in html.lower() or '进度' in html

    def test_publish_result_display(self, client):
        """Given compose page, then it should show success/failure result per platform."""
        resp = client.get("/compose")
        html = resp.text
        # 应有结果展示区域
        assert 'success' in html.lower() or 'success' in html or '成功' in html
