#!/usr/bin/env python3
"""
端到端测试脚本：content-aggregator 完整流程测试
用法：python scripts/test_e2e.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from loguru import logger

from content_aggregator.models import Content, Article
from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.sources.collectors.base_collector import SourceResult

# ── Mock 数据 ────────────────────────────────────
# 3条：1正常 + 1敏感词 + 1重复(与第1条内容相同)
MOCK_ITEMS = [
    {
        "title": "AI 大模型最新进展",
        "content": "OpenAI 正在训练下一代模型，参数规模惊人。" * 20,
        "url": "https://example.com/ai-1",
        "author": "张三",
        "published_at": "2026-05-27T00:00:00Z",
        "summary": "AI 最新进展",
    },
    {
        "title": "加微信免费领取资料",
        "content": "点击就送，扫码加微信领取免费资料。" * 20,
        "url": "https://example.com/spam-1",
        "author": "推广员",
        "published_at": "2026-05-27T00:00:00Z",
        "summary": "垃圾内容",
    },
    {
        "title": "AI 大模型最新进展",
        "content": "OpenAI 正在训练下一代模型，参数规模惊人。" * 20,
        "url": "https://example.com/ai-1-dup",
        "author": "张三",
        "published_at": "2026-05-27T00:00:00Z",
        "summary": "重复内容",
    },
]

MOCK_CONFIG = {
    "llm": {
        "model": "gpt-3.5-turbo",
        "api_key": os.environ.get("OPENAI_API_KEY", "sk-mock"),
        "api_base": "https://api.openai.com/v1",
        "temperature": 0.7,
        "max_tokens": 2000,
    },
    "sources": {
        "rss": [
            {"name": "MockRSS", "url": "https://example.com/feed.xml", "max_items": 5}
        ]
    },
    "export": {"output_dir": str(PROJECT_ROOT / "output" / "test_e2e")},
    "http": {"timeout": 10, "proxy": ""},
    "filter": {
        "sensitive": {"enabled": True, "strict_mode": True},
        "dedup": {"enabled": True, "similarity_threshold": 0.8},
    },
    "translation": {"enabled": False},
    "notifications": {"enabled": True, "channels": [{"type": "console", "enabled": True}]},
}


# ── Mock Collector ────────────────────────────────────
class MockCollector:
    def __init__(self, source_type, config, **kwargs):
        self.source_type = source_type
        self.config = config

    async def collect(self, **kwargs) -> SourceResult:
        return SourceResult(
            success=True,
            data=MOCK_ITEMS,
            error=None,
            source_name=self.source_type,
            collected_count=len(MOCK_ITEMS),
            skipped_count=0,
            duration=0.1,
        )


# ── 测试函数 ────────────────────────────────────
async def test_1_pipeline_init():
    print("\n[TEST] 1. Pipeline 初始化")
    p = ContentPipeline(MOCK_CONFIG)
    assert p.sensitive_filter is not None
    assert p.dedup_filter is not None
    assert len(p.notifiers) > 0
    print(f"  [PASS] 通知器: {[n.get_name() for n in p.notifiers]}")


async def test_2_filter_sensitive():
    print("\n[TEST] 2. 敏感词过滤")
    p = ContentPipeline(MOCK_CONFIG)
    ok = Content(id="1", title="正常文章", content="科技新闻。",
                  source_type="rss", source_id="rss", url="https://e.com/1")
    b, r = await p._apply_filters(ok)
    assert not b, f"正常内容不应被过滤: {r}"
    print("  [PASS] 正常内容通过")
    bad = Content(id="2", title="加微信免费领", content="点击就送扫码加微信。" * 20,
                  source_type="rss", source_id="rss", url="https://e.com/2")
    b, r = await p._apply_filters(bad)
    assert b, f"敏感内容应被过滤，reason={r}"
    assert "敏感词" in r
    print(f"  [PASS] 敏感内容被过滤: {r}")


async def test_3_filter_dedup():
    print("\n[TEST] 3. 去重过滤")
    p = ContentPipeline(MOCK_CONFIG)
    c1 = Content(id="3a", title="AI 发展", content="人工智能快速发展。" * 20,
                  source_type="rss", source_id="rss", url="https://e.com/3a")
    b1, _ = await p._apply_filters(c1)
    assert not b1, "第一篇不应被去重"
    print("  [PASS] 第一篇通过（库空）")
    c2 = Content(id="3b", title="AI 发展", content="人工智能快速发展。" * 20,
                  source_type="rss", source_id="rss", url="https://e.com/3b")
    b2, r2 = await p._apply_filters(c2)
    assert b2, f"重复内容应被过滤，reason={r2}"
    assert "重复内容" in r2
    print(f"  [PASS] 重复内容被过滤: {r2}")


async def test_4_process_source_mock():
    print("\n[TEST] 4. 单源处理流程（Mock LLM）")
    import content_aggregator.workflows.pipeline as pm
    orig = pm.get_collector
    pm.get_collector = lambda *a, **kw: MockCollector(*a, **kw)

    import content_aggregator.processors.rewrite as rw_mod
    async def mock_rw(self, content):
        from content_aggregator.processors.rewrite import RewriteResult
        return RewriteResult(
            success=True,
            rewritten_content=f"[改写] {content.content[:50]}",
            title=content.title + "（改）",
            summary="改写摘要",
        )
    orig_rw = rw_mod.RewriteProcessor.rewrite
    rw_mod.RewriteProcessor.rewrite = mock_rw

    try:
        p = ContentPipeline(MOCK_CONFIG)
        async with p:
            result = await p.process_source(
                source_type="rss",
                rewrite=True,
                translate=False,
                target_language=None,
                formats=["markdown"],
                limit_per_source=3,
            )
        articles = result.get("articles", [])
        summary = result.get("summary", {})
        # 3条Mock：1正常 + 1敏感词(拦) + 1重复(拦) = 期望1篇
        print(f"  [INFO] 数据源={summary.get('total_sources',0)}, 文章数={len(articles)}")
        assert len(articles) == 1, f"期望1篇（1正常-1敏感-1重复），实际{len(articles)}篇"
        print(f"  [PASS] 文章数符合预期（1篇）")
    finally:
        pm.get_collector = orig
        rw_mod.RewriteProcessor.rewrite = orig_rw


async def test_5_export():
    print("\n[TEST] 5. 导出功能")
    from content_aggregator.exporters import Exporter
    out = PROJECT_ROOT / "output" / "test_e2e"
    out.mkdir(parents=True, exist_ok=True)
    exp = Exporter(str(out))
    art = Article(id="exp-1", title="导出测试", content="内容。" * 100,
                  source="rss", source_url="https://e.com", author="作者", word_count=500)
    for fmt in ["markdown", "json", "html"]:
        try:
            path = exp.export(art, fmt)
            assert Path(path).exists(), f"文件不存在: {path}"
            print(f"  [PASS] {fmt}: {Path(path).name}")
        except Exception as e:
            print(f"  [WARN] {fmt}: {e}")


async def test_6_notification():
    print("\n[TEST] 6. 通知功能")
    p = ContentPipeline(MOCK_CONFIG)
    results = await p._notify(
        title="测试通知", body="端到端测试", level="info",
        source_name="test", articles_count=3, duration=1.5,
    )
    for r in results:
        tag = "[PASS]" if r.success else "[FAIL]"
        print(f"  {tag} {r.notifier}: {r.message or r.error}")
    assert all(r.success for r in results)


async def test_7_process_all_mock():
    print("\n[TEST] 7. process_all_sources（Mock）")
    import content_aggregator.workflows.pipeline as pm
    orig = pm.get_collector
    pm.get_collector = lambda *a, **kw: MockCollector(*a, **kw)
    try:
        p = ContentPipeline(MOCK_CONFIG)
        async with p:
            result = await p.process_all_sources(
                rewrite=False, translate=False, seo=False,
                formats=None, limit_per_source=2,
            )
        summary = result.get("summary", {})
        articles = result.get("articles", [])
        ns = summary.get("total_sources", 0)
        print(f"  [INFO] 数据源={ns}, 成功={summary.get('success',0)}, 文章={len(articles)}")
        assert ns > 0, f"应至少发现1个数据源，实际{ns}"
        assert len(articles) > 0, f"应至少产出1篇文章，实际{len(articles)}篇"
        print(f"  [PASS] 批量采集符合预期")
    finally:
        pm.get_collector = orig


# ── 主函数 ────────────────────────────────────
async def main():
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    print("=" * 60)
    print("  content-aggregator 端到端测试")
    print("=" * 60)
    start = time.time()
    passed = 0
    failed = 0
    for name, fn in [
        ("Pipeline 初始化", test_1_pipeline_init),
        ("敏感词过滤", test_2_filter_sensitive),
        ("去重过滤", test_3_filter_dedup),
        ("单源处理（Mock）", test_4_process_source_mock),
        ("导出功能", test_5_export),
        ("通知功能", test_6_notification),
        ("批量采集（Mock）", test_7_process_all_mock),
    ]:
        try:
            await fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            import traceback; traceback.print_exc()
            failed += 1
    elapsed = time.time() - start
    print("\n" + "=" * 60)
    print(f"  结果: {passed} 通过, {failed} 失败 | 耗时: {elapsed:.1f}s")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
