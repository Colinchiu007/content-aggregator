#!/usr/bin/env python3
"""
测试改写功能（调试版本，带详细日志）
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from content_aggregator.models import Content
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy

# 配置日志（详细输出）
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

async def test_rewrite():
    """测试改写功能"""
    print("=" * 60)
    print("测试改写功能（调试版本）")
    print("=" * 60)
    
    # 1. 加载配置
    print("\n[1] 加载配置...")
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    print(f"  LLM Provider: {config['llm']['provider']}")
    print(f"  LLM Model: {config['llm']['model']}")
    print(f"  LLM Base URL: {config['llm']['base_url']}")
    print(f"  Rewrite Strategy: {config['rewrite']['strategy']}")
    
    # 2. 创建测试内容
    print("\n[2] 创建测试内容...")
    test_content = Content(
        id="test-001",
        source_id="test",
        source_type="test",
        url="https://example.com/test",
        title="测试文章标题：人工智能发展趋势",
        content="""
人工智能（AI）是当今科技领域最热门的话题之一。近年来，随着深度学习技术的突破，
AI 在图像识别、自然语言处理、自动驾驶等领域取得了巨大进展。

本文将从以下几个方面探讨 AI 的发展趋势：
1. 大语言模型（LLM）的崛起
2. 多模态 AI 的发展
3. AI 在行业中的应用
4. 未来挑战与机遇

希望通过本文，读者能对 AI 的现状和未来有更清晰的认识。
        """.strip(),
        author="测试作者",
        published_at=None,
        summary="测试摘要",
        metadata={}
    )
    print(f"  标题: {test_content.title}")
    print(f"  内容长度: {len(test_content.content)} 字符")
    
    # 3. 创建改写处理器
    print("\n[3] 创建改写处理器...")
    processor = RewriteProcessor(config)
    
    # 4. 执行改写
    print("\n[4] 开始改写（观察日志输出）...")
    print("-" * 60)
    
    try:
        async with processor:
            result = await processor.rewrite(
                test_content,
                RewriteConfig(strategy=RewriteStrategy.PARAPHRASE)
            )
        
        print("-" * 60)
        print("\n[5] 改写结果:")
        print(f"  成功: {result.success}")
        print(f"  标题: {result.title}")
        print(f"  摘要: {result.summary[:100] if result.summary else '(无)'}")
        print(f"  改写后长度: {len(result.rewritten_content)} 字符")
        print(f"  耗时: {result.duration:.2f}秒")
        
        if result.error:
            print(f"\n  错误: {result.error}")
        
        if result.success and result.rewritten_content:
            print("\n  改写后内容（前500字符）:")
            print(result.rewritten_content[:500])
            print("...\n")
        
    except Exception as e:
        print(f"\n❌ 改写失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_rewrite())
