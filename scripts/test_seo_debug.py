#!/usr/bin/env python
"""SEO 调试脚本 - 打印 LLM 原始响应"""
import sys
import os
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(message)s')

from content_aggregator.processors.seo import SEOProcessor, SEOConfig
from content_aggregator.models import Content


def load_config(config_path: str | None = None) -> dict:
    """加载配置文件"""
    import yaml
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).parent.parent / "config" / "config.yaml"
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {
        "llm": {
            "provider": "deepseek", "api_key": "", "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com", "max_tokens": 4096,
            "timeout": 120, "retry": 3,
        },
        "export": {"output_dir": "./output/exports"},
    }


async def main():
    config = load_config(os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml'))
    seo_config = SEOConfig(**config.get('seo', {}))
    content = Content(
        id="test-001",
        source_id="test-source",
        source_type="test",
        title="AI 技术发展趋势",
        content="人工智能技术正在快速发展，大模型在自然语言处理、计算机视觉等领域取得了显著进展。本文探讨了 AI 技术的发展趋势和应用前景。",
    )

    print("=" * 60)
    print(f"标题: {content.title}")
    print(f"内容: {content.content[:50]}...")
    print("=" * 60)

    try:
        async with SEOProcessor(config) as processor:
            result = await processor.optimize(content, seo_config)
            print(f"\n成功: {result.success}")
            print(f"关键词: {result.keywords}")
            print(f"描述: {result.meta_description}")
            print(f"标题: {result.meta_title}")
            print(f"标签: {result.optimized_tags}")
            if result.error:
                print(f"错误: {result.error}")
            print(f"耗时: {result.duration:.2f}s")
    except Exception as e:
        print(f"\n异常: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
