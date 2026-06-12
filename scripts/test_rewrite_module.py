"""
LLM 改写器模块测试脚本

测试内容：
1. 单篇文章改写
2. Token 使用统计
3. 错误处理
"""

import asyncio
import sys

sys.path.insert(0, "src")

from content_aggregator.processors.rewrite import (
    RewriteProcessor,
    RewriteConfig,
    RewriteStrategy,
)
from content_aggregator.models import Content


async def test_rewrite():
    """测试改写功能"""
    # 从 config.yaml 读取配置
    import yaml
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    import uuid
    from datetime import datetime

    # 测试内容
    content = Content(
        id=str(uuid.uuid4()),
        source_id="test-source",
        source_type="test",
        title="测试文章：人工智能的发展",
        content="""人工智能（Artificial Intelligence，简称 AI）是计算机科学的一个分支，
旨在研究和开发能够模拟、延伸和扩展人类智能的理论、方法、技术及应用系统。

近年来，随着深度学习技术的突破，人工智能在图像识别、自然语言处理、
语音识别等领域取得了显著进展。大语言模型（如 GPT、Claude、DeepSeek）
的出现更是将 AI 的能力推向了新的高度。

未来，人工智能将在医疗、教育、金融、交通等众多领域发挥重要作用，
深刻改变人类的生产和生活方式。
        """.strip(),
        url="https://example.com/test",
        published_at=datetime.now(),
        metadata={"source": "test"}
    )

    print("=" * 60)
    print("LLM 改写器模块测试")
    print("=" * 60)

    async with RewriteProcessor(config) as processor:
        # 测试 1: 深度改写
        print("\n[测试 1] 深度改写 (REWRITE)...")
        result = await processor.rewrite(
            content,
            RewriteConfig(strategy=RewriteStrategy.REWRITE, target_word_count=500)
        )

        if result.success:
            print(f"  [OK] Rewrite success")
            print(f"  Title: {result.title}")
            print(f"  Summary: {result.summary[:100]}...")
            print(f"  Content length: {len(result.rewritten_content)} chars")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Token: {result.metadata.get('tokens_used', 'N/A')}")
            print(f"\n  Preview:\n  {result.rewritten_content[:300]}...")
        else:
            print(f"  [FAIL] Rewrite failed: {result.error}")

        # 测试 2: 摘要提取
        print("\n[测试 2] 摘要提取 (SUMMARIZE)...")
        result2 = await processor.rewrite(
            content,
            RewriteConfig(strategy=RewriteStrategy.SUMMARIZE)
        )

        if result2.success:
            print(f"  [OK] Summarize success")
            print(f"  Summary: {result2.summary}")
        else:
            print(f"  [FAIL] Summarize failed: {result2.error}")


if __name__ == "__main__":
    asyncio.run(test_rewrite())