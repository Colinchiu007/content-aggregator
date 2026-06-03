#!/usr/bin/env python3
"""测试 limit_per_source 参数是否生效"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.models import SourceConfig

async def test_limit_per_source():
    """测试 limit_per_source 参数注入"""
    
    # 创建 pipeline 实例
    pipeline = ContentPipeline(
        http_config={"timeout": 30},
        proxy=None,
        rewrite_config={},
        translation_config={},
    )
    
    # 测试配置：YouTube 频道，限制3条
    test_sources = [
        {
            "name": "YouTube Test Channel",
            "type": "youtube",
            "channel_id": "UCtR5okwgTMghi_uyWvbloEg",  # 示例频道ID
            "api_key": "test_key",  # 会触发 API 错误，但我们要测试参数传递
        }
    ]
    
    print("=" * 60)
    print("测试 limit_per_source=3 参数注入")
    print("=" * 60)
    
    try:
        # 调用 pipeline.process_sources（会调用 collector.collect）
        # 我们期望：即使 YouTube API 调用失败，也能看到参数传递的日志
        results = await pipeline.process_sources(
            sources=test_sources,
            limit_per_source=3,  # 关键参数
            rewrite=False,
            translate=False,
        )
        
        print("\n测试结果:")
        for r in results:
            print(f"  源: {r.get('source_name')}, 成功: {r.get('success')}, 错误: {r.get('error')}")
            
    except Exception as e:
        print(f"\n预期中的错误（测试参数传递）: {e}")
        
    print("\n检查 pipeline.log 或控制台输出，确认是否有 'max_results': 3")
    print("如果看到，说明 limit_per_source 参数注入成功")

if __name__ == "__main__":
    asyncio.run(test_limit_per_source())
