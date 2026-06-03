#!/usr/bin/env python
"""测试三个新采集器"""
import sys
import asyncio
sys.path.insert(0, 'src')

from content_aggregator.sources.collectors.wangyi_collector import WangYiCollector
from content_aggregator.sources.collectors.weibo_hot_collector import WeiboHotCollector
from content_aggregator.sources.collectors.douyin_hot_collector import DouyinHotCollector

async def test_wangyi():
    print("=" * 60)
    print("测试：网易新闻")
    print("=" * 60)
    collector = WangYiCollector(config={"channels": ["news"], "limit": 3})
    result = await collector.collect()
    print(f"Success: {result.success}")
    print(f"Collected: {result.collected_count}")
    print(f"Error: {result.error}")
    for i, item in enumerate(result.data[:5]):
        print(f"  [{i}] {item.get('title', '')[:80]}")
        print(f"       URL: {item.get('url', '')[:80]}")
    return result

async def test_weibo():
    print("=" * 60)
    print("测试：微博热点")
    print("=" * 60)
    collector = WeiboHotCollector(config={"limit": 5})
    result = await collector.collect()
    print(f"Success: {result.success}")
    print(f"Collected: {result.collected_count}")
    print(f"Error: {result.error}")
    for i, item in enumerate(result.data[:5]):
        print(f"  [{i}] #{item.get('word', '')}# [{item.get('heat_label', '')}]")
        print(f"       URL: {item.get('url', '')[:80]}")
    return result

async def test_douyin():
    print("=" * 60)
    print("测试：抖音热点")
    print("=" * 60)
    collector = DouyinHotCollector(config={"limit": 5})
    result = await collector.collect()
    print(f"Success: {result.success}")
    print(f"Collected: {result.collected_count}")
    print(f"Error: {result.error}")
    for i, item in enumerate(result.data[:5]):
        print(f"  [{i}] #{item.get('word', '')}# [{item.get('heat_label', '')}] 热度:{item.get('hot_value', 0)}")
        print(f"       URL: {item.get('url', '')[:80]}")
    return result

async def main():
    await test_wangyi()
    print()
    await test_weibo()
    print()
    await test_douyin()

asyncio.run(main())
