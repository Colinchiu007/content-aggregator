"""
测试 Content 模型
"""

import pytest
from content_aggregator.models import Content


class TestContent:
    """测试 Content 数据类"""
    
    def test_create_minimal(self):
        """测试创建最小 Content 对象"""
        content = Content(title="测试标题")
        
        assert content.title == "测试标题"
        assert content.content == ""  # 默认值
        assert content.url == ""  # 默认值
        assert content.source_id == ""  # 默认值
        assert content.published_date is None  # 默认值
    
    def test_create_full(self):
        """测试创建完整 Content 对象"""
        from datetime import datetime
        
        content = Content(
            title="测试标题",
            content="测试内容",
            url="https://example.com/article/1",
            source_id="test-source",
            published_date=datetime(2026, 5, 28, 12, 0, 0)
        )
        
        assert content.title == "测试标题"
        assert content.content == "测试内容"
        assert content.url == "https://example.com/article/1"
        assert content.source_id == "test-source"
        assert content.published_date == datetime(2026, 5, 28, 12, 0, 0)
    
    def test_to_dict(self):
        """测试 to_dict() 方法"""
        content = Content(
            title="测试标题",
            content="测试内容",
            url="https://example.com/article/1"
        )
        
        result = content.to_dict()
        
        assert isinstance(result, dict)
        assert result["title"] == "测试标题"
        assert result["content"] == "测试内容"
        assert result["url"] == "https://example.com/article/1"
    
    def test_from_dict(self):
        """测试 from_dict() 类方法"""
        data = {
            "title": "测试标题",
            "content": "测试内容",
            "url": "https://example.com/article/1",
            "source_id": "test-source"
        }
        
        content = Content.from_dict(data)
        
        assert content.title == "测试标题"
        assert content.content == "测试内容"
        assert content.url == "https://example.com/article/1"
        assert content.source_id == "test-source"
    
    def test_equality(self):
        """测试相等性比较"""
        content1 = Content(title="标题", url="https://example.com/1")
        content2 = Content(title="标题", url="https://example.com/1")
        content3 = Content(title="不同标题", url="https://example.com/2")
        
        # dataclass 自动生成 __eq__ 方法
        assert content1 == content2
        assert content1 != content3
    
    def test_repr(self):
        """测试 repr 表示"""
        content = Content(title="测试标题", url="https://example.com/1")
        
        repr_str = repr(content)
        
        assert "Content" in repr_str
        assert "测试标题" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
