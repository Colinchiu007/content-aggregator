"""
测试 RewriteResult 模型
"""

import pytest
from content_aggregator.models import RewriteResult, Content


class TestRewriteResult:
    """测试 RewriteResult 数据类"""
    
    def test_create_minimal(self):
        """测试创建最小 RewriteResult 对象"""
        result = RewriteResult(success=True)
        
        assert result.success is True
        assert result.title == ""  # 默认值
        assert result.original_content == ""  # 默认值
        assert result.rewritten_content == ""  # 默认值
        assert result.provider == ""  # 默认值
        assert result.model == ""  # 默认值
        assert result.error == ""  # 默认值
    
    def test_create_full(self):
        """测试创建完整 RewriteResult 对象"""
        result = RewriteResult(
            success=True,
            title="改写后的标题",
            original_content="原始内容",
            rewritten_content="改写后内容",
            provider="openai",
            model="gpt-4",
            error=""
        )
        
        assert result.success is True
        assert result.title == "改写后的标题"
        assert result.original_content == "原始内容"
        assert result.rewritten_content == "改写后内容"
        assert result.provider == "openai"
        assert result.model == "gpt-4"
        assert result.error == ""
    
    def test_create_failure(self):
        """测试创建失败的 RewriteResult"""
        result = RewriteResult(
            success=False,
            error="API 调用失败"
        )
        
        assert result.success is False
        assert result.error == "API 调用失败"
        assert result.rewritten_content == ""  # 失败时没有改写内容
    
    def test_to_dict(self):
        """测试 to_dict() 方法"""
        result = RewriteResult(
            success=True,
            title="标题",
            rewritten_content="内容",
            provider="openai",
            model="gpt-4"
        )
        
        data = result.to_dict()
        
        assert isinstance(data, dict)
        assert data["success"] is True
        assert data["title"] == "标题"
        assert data["rewritten_content"] == "内容"
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4"
    
    def test_from_dict(self):
        """测试 from_dict() 类方法"""
        data = {
            "success": True,
            "title": "标题",
            "rewritten_content": "内容",
            "provider": "openai",
            "model": "gpt-4"
        }
        
        result = RewriteResult.from_dict(data)
        
        assert result.success is True
        assert result.title == "标题"
        assert result.rewritten_content == "内容"
        assert result.provider == "openai"
        assert result.model == "gpt-4"
    
    def test_with_content_object(self):
        """测试与 Content 对象关联"""
        content = Content(title="原始标题", content="原始内容")
        result = RewriteResult(
            success=True,
            title="改写后标题",
            original_content=content.content,
            rewritten_content="改写后内容",
            provider="openai"
        )
        
        # 验证可以存储原始内容
        assert result.original_content == "原始内容"
        assert result.rewritten_content == "改写后内容"
        
        # 验证可以创建新的 Content 对象
        new_content = Content(
            title=result.title,
            content=result.rewritten_content,
            source_id=content.source_id
        )
        assert new_content.title == "改写后标题"
        assert new_content.content == "改写后内容"
    
    def test_repr(self):
        """测试 repr 表示"""
        result = RewriteResult(success=True, title="测试标题")
        
        repr_str = repr(result)
        
        assert "RewriteResult" in repr_str
        assert "success=True" in repr_str
    
    def test_equality(self):
        """测试相等性比较"""
        result1 = RewriteResult(success=True, title="标题")
        result2 = RewriteResult(success=True, title="标题")
        result3 = RewriteResult(success=False, title="不同")
        
        # dataclass 自动生成 __eq__ 方法
        assert result1 == result2
        assert result1 != result3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
