#!/usr/bin/env python3
"""
测试改写功能（带进度回调）
"""
import asyncio
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from content_aggregator.models import Content
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
from content_aggregator.workflows.pipeline import ContentPipeline

# 配置日志（详细输出）
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

async def progress_callback(current, total, message, percentage):
    """进度回调函数（ASCII 版本，避免 Windows 编码问题）"""
    bar_length = 30
    filled_length = int(bar_length * current // total)
    bar = '#' * filled_length + '.' * (bar_length - filled_length)
    print(f"\r进度: [{bar}] {current}/{total} ({percentage}%) - {message}", end='', flush=True)
    if current == total:
        print()  # 换行

async def test_rewrite_with_progress():
    """测试带进度回调的改写功能"""
    print("=" * 60)
    print("测试改写功能（带进度回调）")
    print("=" * 60)
    
    # 1. 加载配置
    print("\n[1] 加载配置...")
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    print(f"  LLM Model: {config['llm']['model']}")
    print(f"  Rewrite Strategy: {config['rewrite']['strategy']}")
    
    # 2. 创建测试内容列表（多篇文章）
    print("\n[2] 创建测试内容列表...")
    test_contents = []
    for i in range(3):  # 测试3篇文章
        content = Content(
            id=f"test-{i+1:03d}",
            source_id="test",
            source_type="test",
            url=f"https://example.com/test/{i+1}",
            title=f"测试文章 {i+1}：人工智能发展趋势",
            content=f"""
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
        test_contents.append(content)
    
    print(f"  创建 {len(test_contents)} 篇测试文章")
    
    # 3. 创建改写处理器
    print("\n[3] 创建改写处理器...")
    processor = RewriteProcessor(config)
    
    # 4. 执行改写（带进度回调）
    print("\n[4] 开始改写（观察进度条）...")
    print("-" * 60)
    
    start_time = time.time()
    results = []
    total = len(test_contents)
    
    try:
        async with processor:
            for i, content in enumerate(test_contents):
                # 报告进度
                progress = int(i / total * 100) if total > 0 else 0
                await progress_callback(i, total, f"正在改写: {content.title[:30]}", progress)
                
                # 改写单篇
                result = await processor.rewrite(content, RewriteConfig(strategy=RewriteStrategy.PARAPHRASE))
                results.append(result)
                
                # 报告完成
                progress = int((i + 1) / total * 100) if total > 0 else 100
                await progress_callback(i + 1, total, f"完成改写: {content.title[:30]}", progress)
        
        elapsed = time.time() - start_time
        print("-" * 60)
        print(f"\n[5] 改写完成:")
        print(f"  成功: {sum(1 for r in results if r.success)}/{len(results)} 篇")
        print(f"  总耗时: {elapsed:.1f}秒")
        print(f"  平均速度: {elapsed/len(results):.1f}秒/篇")
        
        # 显示前2篇文章的标题和长度
        for i, result in enumerate(results[:2]):
            if result.success:
                print(f"\n  文章 {i+1}:")
                print(f"    标题: {result.title[:50]}")
                print(f"    长度: {len(result.rewritten_content)} 字符")
        
    except Exception as e:
        print(f"\n[ERROR] 改写失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_rewrite_with_progress())
