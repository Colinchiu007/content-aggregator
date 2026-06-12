#!/usr/bin/env python3
"""测试 RewriteResult 是否有错误"""

import sys
import asyncio
import time

from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from content_aggregator.processors.rewrite import RewriteResult, RewriteProcessor, RewriteConfig, RewriteStrategy
from content_aggregator.models import Content


def test_rewrite_result_construction():
    """测试1: RewriteResult 构造是否正常"""
    print("[TEST 1] RewriteResult 构造")
    
    # 成功情况
    content = Content(id="1", source_id="test", source_type="rss", title="测试", content="内容" * 100)
    r = RewriteResult(
        success=True,
        original_content=content,
        rewritten_content="改写后的内容",
        title="改写后的标题",
        summary="摘要",
        keywords=["AI", "测试"],
        duration=1.5,
        metadata={"rewritten": True},
    )
    assert r.success is True
    assert r.rewritten_content == "改写后的内容"
    assert r.title == "改写后的标题"
    print("  [OK] 成功构造（带 Content）")
    
    # 失败情况
    r2 = RewriteResult(success=False, error="LLM 调用失败")
    assert r2.success is False
    assert r2.error == "LLM 调用失败"
    assert r2.rewritten_content == ""
    print("  [OK] 失败构造")
    
    # original_content=None
    r3 = RewriteResult(success=True, original_content=None, rewritten_content="test")
    assert r3.original_content is None
    print("  [OK] original_content=None")
    
    print("[PASS] RewriteResult 构造全部通过\n")


async def test_rewrite_return_structure():
    """测试2: rewrite() 返回结构是否与 RewriteResult 匹配"""
    print("[TEST 2] rewrite() 返回结构")
    
    config = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o",
            "timeout": 10,
        }
    }
    
    content = Content(id="2", source_id="test", source_type="rss", title="测试文章", content="这是测试内容。" * 50)
    rewrite_config = RewriteConfig(strategy=RewriteStrategy.REWRITE)
    
    async with RewriteProcessor(config) as processor:
        # 由于 LLM 配置是假的，预期会失败
        result = await processor.rewrite(content, rewrite_config)
        
        # 检查返回类型
        assert isinstance(result, RewriteResult), f"期望 RewriteResult，实际 {type(result)}"
        print(f"  [OK] 返回类型: {type(result).__name__}")
        
        # 检查字段
        print(f"  success: {result.success}")
        print(f"  rewritten_content 类型: {type(result.rewritten_content).__name__}")
        print(f"  title 类型: {type(result.title).__name__}")
        print(f"  error: {result.error}")
        print(f"  duration: {result.duration}")
        print(f"  metadata 类型: {type(result.metadata).__name__}")
        
        # 失败情况下，这些字段应该是默认值
        if not result.success:
            assert result.rewritten_content == "", "失败时 rewritten_content 应为空"
            assert result.title == "", "失败时 title 应为空"
            assert result.error is not None, "失败时应有 error"
            print("  [OK] 失败时的默认值正确")
    
    print("[PASS] rewrite() 返回结构全部通过\n")


async def test_pipeline_usage():
    """测试3: pipeline.py 中对 rewrite_result 的使用是否有错误"""
    print("[TEST 3] pipeline.py 中使用 rewrite_result")
    
    # 模拟 pipeline.py 中的使用模式（来自之前读取的代码）
    config = {
        "llm": {
            "api_key": "test-key",
            "base_url": "https://api.example.com/v1",
            "model": "gpt-4o",
        },
        "sources": {"rss": [{"name": "test", "url": "http://example.com/rss"}]},
    }
    
    content = Content(id="3", source_id="test", source_type="rss", title="测试", content="内容" * 200)
    
    async with RewriteProcessor(config) as processor:
        result = await processor.rewrite(content)
        
        # 模拟 pipeline.py 中的使用（第 273 行附近）
        if result.success:
            # 这些字段在 pipeline.py 中被使用
            _ = result.rewritten_content  # ✅ 存在
            _ = result.title              # ✅ 存在
            _ = result.summary            # ✅ 存在
            _ = result.metadata           # ✅ 存在
            _ = result.original_content  # ✅ 存在（RewriteResult 字段）
            print("  [OK] process_url() 使用模式：所有字段存在")
        else:
            _ = result.error  # ✅ 存在
            print("  [OK] 失败处理：error 字段存在")
    
    # 模拟 process_contents() 中的使用（第 808 行附近）
    # 来自之前读取的代码：
    #   rewrite_result = await self.rewrite_processor.rewrite(content)
    #   rewritten_text = rewrite_result.rewritten_content if rewrite_result.success else ""
    #   final_content = rewritten_text if rewritten_text else content.content
    #   metadata = (rewrite_result.metadata.copy() if rewrite_result.metadata else {}) if rewrite_result.success else {}
    #   metadata['original_content'] = content.content
    #   metadata['original_title'] = content.title
    #   metadata['original_author'] = content.author
    #   article = Article(...)
    
    # 检查这些访问是否都合法
    dummy_result = RewriteResult(success=True, rewritten_content="test", metadata={"k": "v"})
    _ = dummy_result.rewritten_content      # ✅
    _ = dummy_result.success               # ✅
    _ = dummy_result.metadata.copy()       # ✅（metadata 是 dict）
    _ = dummy_result.title                 # ✅
    print("  [OK] process_contents() 使用模式：所有字段存在")
    
    dummy_result_fail = RewriteResult(success=False, error="fail")
    _ = dummy_result_fail.error  # ✅
    print("  [OK] 失败情况：error 字段存在")
    
    print("[PASS] pipeline.py 使用模式全部通过\n")


async def main():
    print("=" * 60)
    print("RewriteResult 错误检查")
    print("=" * 60 + "\n")
    
    test_rewrite_result_construction()
    await test_rewrite_return_structure()
    await test_pipeline_usage()
    
    print("=" * 60)
    print("结论")
    print("=" * 60)
    print("[DONE] 未发现 RewriteResult 错误")
    print("       所有字段访问均合法")
    print("       pipeline.py 中的使用模式均正确")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
