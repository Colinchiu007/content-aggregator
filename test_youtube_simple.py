#!/usr/bin/env python3
"""简单测试 YouTube 采集器"""

import asyncio
import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from content_aggregator.collectors.youtube_collector import YouTubeCollector

async def test():
    """测试 YouTube 采集"""
    
    print("测试 YouTube 采集器...")
    
    # 使用配置文件中的 API Key
    api_key = "AIzaSyDSPReSDrzCFuQZIea0IKNGZENc_X5vW5A"
    
    # 创建采集器（使用代理）
    collector = YouTubeCollector(
        api_key=api_key,
        proxy="http://127.0.0.1:7890"  # 你的代理地址
    )
    
    print(f"API Key: {api_key[:10]}...")
    print(f"Proxy: {collector.proxy}")
    
    # 测试频道采集
    print("\n1. 测试频道采集 (limit_per_source=3)...")
    try:
        from content_aggregator.models import SourceResult
        result = await collector.collect(
            channel_id="UCtR5okwgTMghi_uyWvbloEg",
            max_results=3  # 对应 limit_per_source
        )
        
        print(f"结果: success={result.success}, collected={result.collected_count}, error={result.error}")
        
        if result.data:
            print(f"返回了 {len(result.data)} 篇文章:")
            for i, item in enumerate(result.data[:3], 1):
                print(f"  {i}. {item.get('title', 'N/A')}")
        elif result.error:
            print(f"错误: {result.error}")
            
    except Exception as e:
        print(f"异常: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n2. 测试搜索采集...")
    try:
        result = await collector.collect(
            query="AI",
            max_results=3
        )
        
        print(f"结果: success={result.success}, collected={result.collected_count}, error={result.error}")
        
        if result.data:
            print(f"返回了 {len(result.data)} 篇文章")
            
    except Exception as e:
        print(f"异常: {e}")

if __name__ == "__main__":
    asyncio.run(test())
