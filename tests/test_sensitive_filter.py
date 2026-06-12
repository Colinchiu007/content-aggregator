"""
测试敏感词过滤器
"""

import pytest
import asyncio
from content_aggregator.processors.filter.sensitive import SensitiveFilter, SensitiveFilterConfig


class TestSensitiveFilterConfig:
    """测试 SensitiveFilterConfig 配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = SensitiveFilterConfig()
        
        assert config.enabled is True
        assert config.mode == "blacklist"
        assert config.match_type == "contains"
        assert config.case_sensitive is False
        assert config.words_file == "config/sensitive_words.txt"
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = SensitiveFilterConfig(
            enabled=False,
            mode="whitelist",
            match_type="regex",
            case_sensitive=True,
            words_file="custom_sensitive.txt"
        )
        
        assert config.enabled is False
        assert config.mode == "whitelist"
        assert config.match_type == "regex"
        assert config.case_sensitive is True
        assert config.words_file == "custom_sensitive.txt"


class TestSensitiveFilter:
    """测试 SensitiveFilter 过滤器"""
    
    @pytest.fixture
    def filter(self):
        """创建测试用的过滤器实例"""
        config = SensitiveFilterConfig(enabled=True, words_file="")
        f = SensitiveFilter(config)
        # 手动添加测试用敏感词
        f._blacklist = {"坏词", "敏感词", "badword"}
        f._whitelist = set()
        return f
    
    @pytest.mark.asyncio
    async def test_no_filtering_when_disabled(self, filter):
        """测试禁用时不进行过滤"""
        filter.config.enabled = False
        
        content = {"title": "包含坏词的文章", "content": "这是内容"}
        result = await filter.process(content)
        
        assert result["success"] is True
        assert result["action"] == "allow"
    
    @pytest.mark.asyncio
    async def test_blacklist_match(self, filter):
        """测试黑名单匹配"""
        content = {"title": "包含坏词的文章", "content": "这是内容"}
        result = await filter.process(content)
        
        assert result["success"] is True
        assert result["is_blocked"] is True
        assert result["action"] == "block"
        assert "坏词" in result["matched_words"]
    
    @pytest.mark.asyncio
    async def test_blacklist_no_match(self, filter):
        """测试黑名单不匹配"""
        content = {"title": "正常文章标题", "content": "这是正常内容"}
        result = await filter.process(content)
        
        assert result["success"] is True
        assert result["is_blocked"] is False
        assert result["action"] == "allow"
        assert len(result["matched_words"]) == 0
    
    @pytest.mark.asyncio
    async def test_case_sensitive(self, filter):
        """测试大小写敏感"""
        filter.config.case_sensitive = True
        filter._blacklist = {"BadWord"}  # 大写
        
        # 小写不应该匹配
        content1 = {"title": "包含 badword 的文章", "content": ""}
        result1 = await filter.process(content1)
        assert result1["is_blocked"] is False
        
        # 大写应该匹配
        content2 = {"title": "包含 BadWord 的文章", "content": ""}
        result2 = await filter.process(content2)
        assert result2["is_blocked"] is True
    
    @pytest.mark.asyncio
    async def test_case_insensitive(self, filter):
        """测试大小写不敏感（默认）"""
        filter.config.case_sensitive = False
        filter._blacklist = {"badword"}
        
        # 大小写混合应该匹配
        content = {"title": "包含 BadWord 的文章", "content": ""}
        result = await filter.process(content)
        
        assert result["is_blocked"] is True
        assert "badword" in result["matched_words"]  # 应该是小写的
    
    def test_load_words_from_file(self):
        """测试从文件加载敏感词"""
        # 创建临时敏感词文件
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False) as f:
            f.write("坏词1\n")
            f.write("坏词2\n")
            f.write("# 这是注释\n")
            f.write("\n")  # 空行
            f.write("坏词3\n")
            temp_path = f.name
        
        try:
            config = SensitiveFilterConfig(words_file=temp_path)
            f = SensitiveFilter(config)
            
            assert "坏词1" in f._blacklist
            assert "坏词2" in f._blacklist
            assert "坏词3" in f._blacklist"
            assert "# 这是注释" not in f._blacklist  # 注释不应该加载
            assert "" not in f._blacklist  # 空行不应该加载
        finally:
            os.unlink(temp_path)
    
    @pytest.mark.asyncio
    async def test_filter_batch(self, filter):
        """测试批量过滤"""
        contents = [
            {"title": "正常文章1", "content": "内容1"},
            {"title": "包含坏词的文章", "content": "内容2"},
            {"title": "正常文章2", "content": "内容3"},
            {"title": "包含敏感词的的文章", "content": "内容4"},
        ]
        
        result = await filter.filter_batch(contents)
        
        assert result["success"] is True
        assert result["total"] == 4
        assert result["blocked_count"] == 2
        assert result["allowed_count"] == 2
        assert len(result["blocked"]) == 2
        assert len(result["allowed"]) == 2
    
    def test_reset(self, filter):
        """测试重置过滤器"""
        # 先添加一些状态
        filter._blocked_count = 10
        filter._total_count = 20
        
        # 重置
        filter.reset()
        
        assert filter._blocked_count == 0
        assert filter._total_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
