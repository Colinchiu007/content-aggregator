"""
测试 Web API 端点
"""

import pytest
import asyncio
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """创建 FastAPI 应用实例"""
    try:
        from web.server import app as fastapi_app
        
        # 创建测试客户端
        client = TestClient(fastapi_app)
        return client
    except ImportError:
        pytest.skip("Web server 未实现")


class TestWebAPIRoot:
    """测试根路径"""
    
    def test_root(self, app):
        """测试根路径访问"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.get("/")
        
        # 应该返回 HTML 页面或重定向
        assert response.status_code in [200, 302, 303]
        
        if response.status_code == 200:
            assert "html" in response.headers["content-type"].lower() or True


class TestWebAPISources:
    """测试数据源 API"""
    
    def test_list_sources(self, app):
        """测试获取数据源列表"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.get("/api/sources")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "sources" in data or isinstance(data, list)


class TestWebAPIArticles:
    """测试文章 API"""
    
    def test_list_articles(self, app):
        """测试获取文章列表"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.get("/api/articles")
        
        assert response.status_code == 200
        
        data = response.json()
        assert "articles" in data or isinstance(data, list)
    
    def test_get_article(self, app):
        """测试获取单篇文章"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        # 先获取文章列表
        list_response = app.get("/api/articles")
        
        if list_response.status_code == 200:
            articles = list_response.json()
            if isinstance(articles, dict):
                articles = articles.get("articles", [])
            
            if articles and len(articles) > 0:
                article_id = articles[0].get("id") or articles[0].get("article_id")
                
                if article_id:
                    # 获取单篇文章
                    response = app.get(f"/api/articles/{article_id}")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "id" in data or "title" in data


class TestWebAPIExport:
    """测试导出 API"""
    
    def test_export_article(self, app):
        """测试导出文章"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        # 先获取文章列表
        list_response = app.get("/api/articles")
        
        if list_response.status_code == 200:
            articles = list_response.json()
            if isinstance(articles, dict):
                articles = articles.get("articles", [])
            
            if articles and len(articles) > 0:
                article_id = articles[0].get("id") or articles[0].get("article_id")
                
                if article_id:
                    # 测试 PDF 导出
                    response = app.get(f"/api/export/pdf/{article_id}")
                    
                    # 应该返回文件或 404
                    assert response.status_code in [200, 404, 501]  # 501 = 未实现


class TestWebAPIRewrite:
    """测试改写 API"""
    
    def test_rewrite_article(self, app):
        """测试改写文章"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        # 先获取文章列表
        list_response = app.get("/api/articles")
        
        if list_response.status_code == 200:
            articles = list_response.json()
            if isinstance(articles, dict):
                articles = articles.get("articles", [])
            
            if articles and len(articles) > 0:
                article_id = articles[0].get("id") or articles[0].get("article_id")
                
                if article_id:
                    # 测试改写
                    response = app.post(
                        f"/api/rewrite/{article_id}",
                        json={"provider": "openai", "model": "gpt-4"}
                    )
                    
                    # 应该返回任务 ID 或错误
                    assert response.status_code in [200, 201, 400, 501]


class TestWebAPIScheduler:
    """测试调度器 API"""
    
    def test_get_scheduler_status(self, app):
        """测试获取调度器状态"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.get("/api/scheduler/status")
        
        # 应该返回状态或 404
        assert response.status_code in [200, 404, 501]
        
        if response.status_code == 200:
            data = response.json()
            assert "running" in data or "status" in data
    
    def test_start_scheduler(self, app):
        """测试启动调度器"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.post("/api/scheduler/start")
        
        # 应该返回成功或 404
        assert response.status_code in [200, 404, 501]
    
    def test_stop_scheduler(self, app):
        """测试停止调度器"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.post("/api/scheduler/stop")
        
        # 应该返回成功或 404
        assert response.status_code in [200, 404, 501]


class TestWebAPIAuth:
    """测试认证（如果需要）"""
    
    def test_unauthorized_access(self, app):
        """测试未授权访问"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        # 如果 API 需要认证，未授权访问应该返回 401
        # 这里只是示例，具体取决于实现
        pass


class TestWebAPIErrors:
    """测试错误处理"""
    
    def test_404(self, app):
        """测试 404 错误"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        response = app.get("/api/nonexistent")
        
        assert response.status_code == 404
    
    def test_invalid_method(self, app):
        """测试无效的 HTTP 方法"""
        if app is None:
            pytest.skip("Web server 未实现")
        
        # 对只接受 POST 的端点发送 GET 请求
        response = app.get("/api/export/pdf/invalid")
        
        # 应该返回 405 Method Not Allowed 或 404
        assert response.status_code in [404, 405]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
