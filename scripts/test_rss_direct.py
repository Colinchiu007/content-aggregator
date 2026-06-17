#!/usr/bin/env python3
"""
直接测试 RSS 采集（绕过 Web UI 和去重）
"""
import sys
import asyncio
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import logging

# 配置日志（显示所有级别）
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_rss_collect():
    """测试 RSS 采集"""
    print("\n" + "="*60)
    print("🧪 直接测试 RSS 采集")
    print("="*60 + "\n")
    
    try:
        # 导入 RSS Collector
        from content_aggregator.collectors.rss import RSSCollector
        
        # 测试配置
        config = {
            "name": "少数派测试",
            "url": "https://sspai.com/feed",
            "enabled": True
        }
        
        print(f"📡 RSS 源: {config['name']}")
        print(f"🔗 URL: {config['url']}\n")
        
        # 创建 Collector
        collector = RSSCollector(config)
        
        # 执行采集
        print("⏳ 开始采集...\n")
        result = await collector.collect()
        
        # 显示结果
        print("\n" + "="*60)
        print("📊 采集结果")
        print("="*60)
        
        if result.get("success"):
            items = result.get("items", [])
            print(f"✅ 成功!")
            print(f"📝 获取到 {len(items)} 条内容\n")
            
            if items:
                print("前 3 条内容:")
                for i, item in enumerate(items[:3], 1):
                    print(f"\n{i}. {item.get('title', '无标题')}")
                    print(f"   链接: {item.get('url', '无链接')}")
                    print(f"   内容长度: {len(item.get('content', ''))} 字符")
            else:
                print("⚠️ 获取到 0 条内容")
        else:
            print(f"❌ 失败!")
            print(f"错误: {result.get('error', '未知错误')}")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_rss_collect())
