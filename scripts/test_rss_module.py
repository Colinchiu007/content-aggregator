"""RSS 采集器测试脚本"""
import sys, json

# 直接引用，避免触发整个包导入
sys.path.insert(0, "src")
sys.path.insert(0, "src/content_aggregator/sources/rss")

from collector import RSSCollector

# 测试 URL：阮一峰博客（直连可访问）
TEST_URLS = [
    ("阮一峰博客", "https://www.ruanyifeng.com/blog/atom.xml"),
    ("知乎日报", "https://rsshub.app/zhihu/daily"),
]


def test_collector():
    for name, url in TEST_URLS:
        print(f"\n{'='*60}")
        print(f"测试: {name}")
        print(f"URL: {url}")
        print("=" * 60)

        collector = RSSCollector(url, max_items=3)

        # 1. 测试连通性
        print("\n[1] 连通性测试...")
        test_result = collector.test_connection()
        print(f"    结果: {test_result}")

        # 2. 采集文章
        print("\n[2] 采集文章...")
        result = collector.collect()

        if result["success"]:
            print(f"    成功! 共 {result['count']} 篇")
            for i, article in enumerate(result["data"], 1):
                print(f"\n    文章 {i}:")
                print(f"      标题: {article.title}")
                print(f"      链接: {article.url}")
                print(f"      作者: {article.author}")
                if article.published_at:
                    print(f"      时间: {article.published_at}")
                print(f"      摘要: {article.summary[:80]}...")
        else:
            print(f"    失败: {result['error']}")


if __name__ == "__main__":
    test_collector()
    print("\n\n测试完成!")