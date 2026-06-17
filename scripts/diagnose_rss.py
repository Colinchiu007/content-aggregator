#!/usr/bin/env python3
"""
完整诊断：测试 RSS 采集（检查代理、网络、Collector）
"""
import sys
import asyncio
import aiohttp
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 配置日志
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_network_connectivity():
    """测试网络连通性"""
    print("\n" + "="*60)
    print("🌐 测试网络连通性")
    print("="*60 + "\n")
    
    # 测试 URL
    test_urls = [
        "https://sspai.com/feed",
        "https://httpbin.org/get",
        "https://www.baidu.com"
    ]
    
    for url in test_urls:
        print(f"📡 测试: {url}")
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, ssl=False) as resp:
                    print(f"   ✅ 状态码: {resp.status}")
                    if resp.status == 200:
                        print(f"   📝 内容长度: {len(await resp.text())} 字符")
                        break  # 有一个成功就够
        except Exception as e:
            print(f"   ❌ 失败: {type(e).__name__}: {e}")
    
    print()

async def test_rss_collect_direct():
    """直接测试 RSS 采集（绕过所有过滤器）"""
    print("\n" + "="*60)
    print("🧪 直接测试 RSS 采集")
    print("="*60 + "\n")
    
    try:
        # 导入 RSS Collector
        from content_aggregator.collectors.rss import RSSCollector
        
        # 测试配置（禁用代理）
        config = {
            "name": "少数派测试",
            "url": "https://sspai.com/feed",
            "enabled": True
        }
        
        print(f"📡 RSS 源: {config['name']}")
        print(f"🔗 URL: {config['url']}")
        print(f"⚙️  配置: {config}\n")
        
        # 创建 Collector
        print("⏳ 创建 RSSCollector...\n")
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
            print(f"✅ 采集成功!")
            print(f"📝 获取到 {len(items)} 条内容\n")
            
            if items:
                print("前 3 条内容:")
                for i, item in enumerate(items[:3], 1):
                    print(f"\n{i}. {item.get('title', '无标题')}")
                    print(f"   链接: {item.get('url', '无链接')}")
                    print(f"   内容长度: {len(item.get('content', ''))} 字符")
            else:
                print("⚠️ 获取到 0 条内容")
                print("\n可能原因:")
                print("  1. RSS 源没有新内容")
                print("  2. RSS 解析失败（格式错误）")
                print("  3. 网络问题（代理配置错误）")
        else:
            print(f"❌ 采集失败!")
            print(f"错误: {result.get('error', '未知错误')}")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n❌ 异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函数"""
    print("\n" + "🚀"*30)
    print("Content Aggregator - RSS 采集诊断工具")
    print("🚀"*30 + "\n")
    
    # 1. 测试网络连通性
    await test_network_connectivity()
    
    # 2. 测试 RSS 采集
    await test_rss_collect_direct()
    
    print("\n✨ 诊断完成！")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
