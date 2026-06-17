"""
测试去重过滤器
"""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path

from content_aggregator.processors.filter.dedup import DedupFilter, DedupFilterConfig


class TestDedupFilterConfig:
    """测试 DedupFilterConfig 配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = DedupFilterConfig()
        
        assert config.enabled is True
        assert config.similarity_threshold == 0.8
        assert config.exact_dedup is True
        assert config.fuzzy_dedup is True
        assert config.min_length == 50
        assert config.cache_file == ""
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = DedupFilterConfig(
            enabled=False,
            similarity_threshold=0.9,
            exact_dedup=False,
            fuzzy_dedup=True,
            min_length=100,
            cache_file="cache/test.json"
        )
        
        assert config.enabled is False
        assert config.similarity_threshold == 0.9
        assert config.exact_dedup is False
        assert config.fuzzy_dedup is True
        assert config.min_length == 100
        assert config.cache_file == "cache/test.json"


class TestDedupFilter:
    """测试 DedupFilter 过滤器"""
    
    @pytest.fixture
    def filter(self):
        """创建测试用的过滤器实例"""
        config = DedupFilterConfig(enabled=True, cache_file="")
        return DedupFilter(config)
    
    @pytest.fixture
    def filter_with_cache(self):
        """创建带缓存的过滤器实例"""
        # 创建临时缓存文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_file = f.name
        
        config = DedupFilterConfig(enabled=True, cache_file=cache_file)
        yield DedupFilter(config)
        
        # 清理
        if Path(cache_file).exists():
            Path(cache_file).unlink()
    
    @pytest.mark.asyncio
    async def test_no_dedup_when_disabled(self, filter):
        """测试禁用时不进行去重"""
        filter.config.enabled = False
        
        content = {"title": "测试文章", "content": "这是内容"}
        result = await filter.process(content)
        
        assert result["success"] is True
        assert result["is_duplicate"] is False
        assert result["action"] == "allow"
    
    @pytest.mark.asyncio
    async def test_exact_dedup(self, filter):
        """测试精确去重（hash 匹配）"""
        content1 = {"title": "测试文章", "content": "这是内容"}
        content2 = {"title": "测试文章", "content": "这是内容"}  # 完全相同
        
        # 第一次处理
        result1 = await filter.process(content1)
        assert result1["is_duplicate"] is False
        assert result1["action"] == "allow"
        
        # 第二次处理（应该检测到重复）
        result2 = await filter.process(content2)
        assert result2["is_duplicate"] is True
        assert result2["action"] == "block"
    
    @pytest.mark.asyncio
    async def test_fuzzy_dedup(self):
        """测试模糊去重（相似度）"""
        config = DedupFilterConfig(
            enabled=True,
            exact_dedup=False,
            fuzzy_dedup=True,
            similarity_threshold=0.8,
            min_length=10
        )
        filter = DedupFilter(config)
        
        content1 = {"title": "测试文章", "content": "这是第一篇测试文章的内容，包含一些关键词"}
        content2 = {"title": "测试文章2", "content": "这是第二篇测试文章的内容，包含一些关键词"}  # 相似
        
        # 第一次处理
        result1 = await filter.process(content1)
        assert result1["is_duplicate"] is False
        
        # 第二次处理（应该检测到相似）
        result2 = await filter.process(content2)
        assert result2["is_duplicate"] is True
        assert len(result2["similar_to"]) > 0
        assert len(result2["similarity_scores"]) > 0
        assert all(s >= 0.8 for s in result2["similarity_scores"])
    
    @pytest.mark.asyncio
    async def test_min_length(self):
        """测试最小长度限制"""
        config = DedupFilterConfig(
            enabled=True,
            fuzzy_dedup=True,
            min_length=100  # 设置较高的最小长度
        )
        filter = DedupFilter(config)
        
        # 短内容不应该进行模糊去重
        content1 = {"title": "短", "content": "短内容"}
        content2 = {"title": "短2", "content": "短内容2"}
        
        result1 = await filter.process(content1)
        result2 = await filter.process(content2)
        
        # 不应该检测到重复（因为内容太短）
        assert result2["is_duplicate"] is False
    
    @pytest.mark.asyncio
    async def test_cache_persistence(self, filter_with_cache):
        """测试缓存持久化"""
        filter = filter_with_cache
        
        # 添加一些内容
        contents = [
            {"title": "文章1", "content": "内容1"},
            {"title": "文章2", "content": "内容2"},
        ]
        
        for content in contents:
            await filter.process(content)
        
        # 手动保存
        filter.save_cache()
        
        # 验证缓存文件存在
        cache_file = Path(filter.config.cache_file)
        assert cache_file.exists()
        
        # 读取缓存文件
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["hashes"]) == 2
            assert len(data["contents"]) == 2
    
    @pytest.mark.asyncio
    async def test_cache_load_on_init(self):
        """测试初始化时加载缓存"""
        # 创建临时缓存文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            cache_file = f.name
            json.dump({
                "hashes": ["hash1", "hash2", "hash3"],
                "contents": [
                    {"title": "文章1", "content": "内容1", "hash": "hash1"}
                ]
            }, f)
        
        try:
            # 创建新的过滤器（应该加载缓存）
            config = DedupFilterConfig(enabled=True, cache_file=cache_file)
            filter = DedupFilter(config)
            
            # 验证加载了缓存
            assert len(filter._seen_hashes) == 3
            assert "hash1" in filter._seen_hashes
            assert "hash2" in filter._seen_hashes
            assert "hash3" in filter._seen_hashes
            assert len(filter._seen_contents) == 1
        
        finally:
            Path(cache_file).unlink()
    
    @pytest.mark.asyncio
    async def test_reset(self, filter):
        """测试重置过滤器"""
        # 先添加一些内容
        content = {"title": "测试", "content": "内容"}
        await filter.process(content)
        
        assert len(filter._seen_hashes) == 1
        
        # 重置
        filter.reset()
        
        assert len(filter._seen_hashes) == 0
        assert len(filter._seen_contents) == 0
    
    @pytest.mark.asyncio
    async def test_shutdown(self, filter_with_cache):
        """测试关闭时保存"""
        filter = filter_with_cache
        
        # 添加内容
        content = {"title": "测试", "content": "内容"}
        await filter.process(content)
        
        # 关闭
        filter.shutdown()
        
        # 验证缓存文件已保存
        cache_file = Path(filter.config.cache_file)
        assert cache_file.exists()
        
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["hashes"]) == 1
    
    @pytest.mark.asyncio
    async def test_filter_batch(self, filter):
        """测试批量去重"""
        contents = [
            {"title": "文章1", "content": "内容1"},
            {"title": "文章2", "content": "内容2"},
            {"title": "文章1", "content": "内容1"},  # 重复
            {"title": "文章2", "content": "内容2"},  # 重复
        ]
        
        result = await filter.filter_batch(contents)
        
        assert result["success"] is True
        assert result["total"] == 4
        assert result["unique_count"] == 2
        assert result["duplicate_count"] == 2
        assert len(result["unique"]) == 2
        assert len(result["duplicates"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
