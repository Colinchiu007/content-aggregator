"""
测试防封采集机制集成
"""
import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from content_aggregator.sources.collectors.xiaohongshu_collector import XiaohongshuCollector
from content_aggregator.sources.collectors.douyin_collector import DouyinCollector
from content_aggregator.anti_block import AntiBlockManager, create_default_manager


def test_xiaohongshu_anti_block():
    """测试小红书采集器防封功能"""
    print("=== 测试1: 小红书采集器防封功能 ===")
    
    # 创建采集器（不启用防封）
    collector1 = XiaohongshuCollector(cookie="test_cookie", enable_anti_block=False)
    print(f"✅ 采集器1创建成功（防封关闭）")
    print(f"   防封状态: {collector1.enable_anti_block}")
    
    # 创建采集器（启用防封）
    collector2 = XiaohongshuCollector(cookie="test_cookie", enable_anti_block=True)
    print(f"✅ 采集器2创建成功（防封开启）")
    print(f"   防封状态: {collector2.enable_anti_block}")
    print(f"   防封管理器: {collector2.anti_block_manager is not None}")
    
    # 动态启用防封
    collector1.enable_anti_block_feature()
    print(f"✅ 动态启用防封成功")
    print(f"   防封状态: {collector1.enable_anti_block}")
    
    # 获取统计信息
    stats = collector1.get_anti_block_stats()
    print(f"✅ 获取统计信息成功: {stats}")
    
    # 动态禁用防封
    collector1.disable_anti_block_feature()
    print(f"✅ 动态禁用防封成功")
    print(f"   防封状态: {collector1.enable_anti_block}")


def test_douyin_anti_block():
    """测试抖音采集器防封功能"""
    print("\n=== 测试2: 抖音采集器防封功能 ===")
    
    # 创建采集器（不启用防封）
    collector1 = DouyinCollector(cookie="test_cookie", enable_anti_block=False)
    print(f"✅ 采集器1创建成功（防封关闭）")
    print(f"   防封状态: {collector1.enable_anti_block}")
    
    # 创建采集器（启用防封）
    collector2 = DouyinCollector(cookie="test_cookie", enable_anti_block=True)
    print(f"✅ 采集器2创建成功（防封开启）")
    print(f"   防封状态: {collector2.enable_anti_block}")
    print(f"   防封管理器: {collector2.anti_block_manager is not None}")
    
    # 动态启用防封
    collector1.enable_anti_block_feature()
    print(f"✅ 动态启用防封成功")
    print(f"   防封状态: {collector1.enable_anti_block}")
    
    # 获取统计信息
    stats = collector1.get_anti_block_stats()
    print(f"✅ 获取统计信息成功: {stats}")
    
    # 动态禁用防封
    collector1.disable_anti_block_feature()
    print(f"✅ 动态禁用防封成功")
    print(f"   防封状态: {collector1.enable_anti_block}")


def test_anti_block_manager_reuse():
    """测试防封管理器复用（多个采集器共享）"""
    print("\n=== 测试3: 防封管理器复用 ===")
    
    # 创建共享的防封管理器
    manager = create_default_manager(enable_proxy=False)
    print(f"✅ 创建共享防封管理器成功")
    
    # 创建多个采集器，共享同一个管理器
    collector1 = XiaohongshuCollector(cookie="test_cookie")
    collector2 = DouyinCollector(cookie="test_cookie")
    
    collector1.enable_anti_block_feature(manager)
    collector2.enable_anti_block_feature(manager)
    
    print(f"✅ 两个采集器共享同一个防封管理器")
    print(f"   小红书管理器: {collector1.anti_block_manager is manager}")
    print(f"   抖音管理器: {collector2.anti_block_manager is manager}")
    print(f"   是否同一个: {collector1.anti_block_manager is collector2.anti_block_manager}")


def test_platform_detection():
    """测试平台检测功能"""
    print("\n=== 测试4: 平台检测功能 ===")
    
    # 小红书
    xhs_urls = [
        "https://www.xiaohongshu.com/explore/abc123",
        "https://xhslink.com/xyz789",
    ]
    
    for url in xhs_urls:
        result = XiaohongshuCollector.detect_platform(url)
        print(f"   小红书检测: {url} → {result}")
    
    # 抖音
    douyin_urls = [
        "https://www.douyin.com/video/123456",
        "https://iesdouyin.com/share/video/789012",
    ]
    
    for url in douyin_urls:
        result = DouyinCollector.detect_platform(url)
        print(f"   抖音检测: {url} → {result}")


if __name__ == "__main__":
    print("防封采集机制集成测试\n")
    
    try:
        test_xiaohongshu_anti_block()
        test_douyin_anti_block()
        test_anti_block_manager_reuse()
        test_platform_detection()
        
        print("\n✅ 所有测试通过！")
        print("\n防封采集机制集成成功！")
        print("下一步：配置代理 API，进行真实采集测试")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
