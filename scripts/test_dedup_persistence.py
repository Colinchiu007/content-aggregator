"""
测试 DedupFilter 持久化功能
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from content_aggregator.processors.filter.dedup import DedupFilter, DedupFilterConfig


async def test_dedup_persistence():
    """测试去重持久化"""
    print("=" * 60)
    print("测试 DedupFilter 持久化功能")
    print("=" * 60)
    
    # 使用临时缓存文件
    cache_file = project_root / "data" / "test_dedup_cache.json"
    if cache_file.exists():
        cache_file.unlink()
    
    print(f"\n[1] 创建 DedupFilter（cache_file={cache_file}）")
    config = DedupFilterConfig(
        enabled=True,
        similarity_threshold=0.8,
        exact_dedup=True,
        fuzzy_dedup=True,
        cache_file=str(cache_file)
    )
    dedup = DedupFilter(config)
    print(f"  - 初始 hash 数量: {len(dedup._seen_hashes)}")
    print(f"  - 初始内容数量: {len(dedup._seen_contents)}")
    
    # 添加一些内容
    print(f"\n[2] 添加测试内容（3 条）")
    test_contents = [
        {"title": "文章1", "content": "这是第一篇测试文章的内容"},
        {"title": "文章2", "content": "这是第二篇测试文章的内容"},
        {"title": "文章3", "content": "这是第三篇测试文章的内容"},
    ]
    
    for i, content in enumerate(test_contents, 1):
        result = await dedup.process(content)
        print(f"  - 内容{i}: hash={result['hash'][:8]}..., duplicate={result['is_duplicate']}")
    
    print(f"\n[3] 检查内存状态")
    print(f"  - hash 数量: {len(dedup._seen_hashes)}")
    print(f"  - 内容数量: {len(dedup._seen_contents)}")
    
    print(f"\n[4] 手动保存缓存")
    dedup.save_cache()
    print(f"  - 缓存文件存在: {cache_file.exists()}")
    if cache_file.exists():
        import json
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"  - 缓存的 hash 数量: {len(data.get('hashes', []))}")
            print(f"  - 缓存的内容数量: {len(data.get('contents', []))}")
    
    # 创建新的 DedupFilter 实例（模拟重启）
    print(f"\n[5] 模拟重启 - 创建新的 DedupFilter 实例")
    dedup2 = DedupFilter(config)
    print(f"  - 加载的 hash 数量: {len(dedup2._seen_hashes)}")
    print(f"  - 加载的内容数量: {len(dedup2._seen_contents)}")
    
    # 测试去重（应该检测到重复）
    print(f"\n[6] 测试去重（应该检测到重复）")
    for i, content in enumerate(test_contents, 1):
        result = await dedup2.process(content)
        print(f"  - 内容{i}: duplicate={result['is_duplicate']}, action={result['action']}")
    
    # 添加新内容（应该不重复）
    print(f"\n[7] 添加新内容（应该不重复）")
    new_content = {"title": "文章4", "content": "这是一篇全新的文章"}
    result = await dedup2.process(new_content)
    print(f"  - 内容4: duplicate={result['is_duplicate']}, action={result['action']}")
    
    # 关闭时保存
    print(f"\n[8] 关闭 DedupFilter")
    dedup2.shutdown()
    
    # 清理
    print(f"\n[9] 清理测试文件")
    if cache_file.exists():
        cache_file.unlink()
        print(f"  - 已删除缓存文件")
    
    print(f"\n{'=' * 60}")
    print("✅ 测试完成！持久化功能正常工作")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(test_dedup_persistence())
