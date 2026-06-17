"""
content-aggregator 全流程端到端测试脚本
"""
import sys
import os
import tempfile
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def run_test(name, fn):
    try:
        ok, msg = fn()
        icon = "[PASS]" if ok else "[FAIL]"
        print("  " + icon + " " + name)
        if msg:
            print("         " + str(msg))
        return ok
    except Exception as e:
        print("  [FAIL] " + name + ": " + str(e))
        return False


# ── 1. 模块导入 ──────────────────────────────────────
def test_imports():
    try:
        from content_aggregator.models import Article, Content
        from content_aggregator.exporters.pdf_exporter import PDFExporter
        from content_aggregator.exporters.html.exporter import HTMLExporter
        from content_aggregator.exporters.json.exporter import JSONExporter
        from content_aggregator.exporters.txt import TXTExporter
        from content_aggregator.exporters.markdown.exporter import MarkdownExporter
        from content_aggregator.exporters.xiaohongshu.exporter import XiaohongshuExporter
        from content_aggregator.processors.rewrite.rewriter import RewriteProcessor
        from content_aggregator.processors.seo import SEOProcessor
        from content_aggregator.processors.filter.sensitive import SensitiveFilter, SensitiveFilterConfig
        from content_aggregator.processors.filter.dedup import DedupFilter, DedupFilterConfig
        from content_aggregator.sources.rss.collector import RSSCollector
        from content_aggregator.workflows.pipeline import ContentPipeline
        return True, ""
    except ImportError as e:
        return False, str(e)


# ── 2. PDF 中文字体注册 ──────────────────────────────
def test_pdf_chinese_font():
    from content_aggregator.exporters.pdf_exporter import PDFExporter
    import yaml
    with open('config/config.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    exporter = PDFExporter(cfg)
    font_name = getattr(exporter, '_chinese_font_name', None)
    return font_name is not None, "font=" + str(font_name)


# ── 3. RSS 采集 ──────────────────────────────────────
def test_rss_collect():
    from content_aggregator.sources.rss.collector import RSSCollector
    import yaml
    with open('config/config.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    collector = RSSCollector(cfg)
    result = collector.collect()
    return isinstance(result, dict), "keys=" + str(list(result.keys())[:3])


# ── 4. LLM Rewriter (async) ──────────────────────────
def test_rewriter():
    from content_aggregator.processors.rewrite.rewriter import RewriteProcessor
    from content_aggregator.models import Content
    import yaml

    with open('config/config.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    content = Content(
        id="rewrite_test_001",
        source_id="rss",
        source_type="rss",
        url="https://example.com/test",
        title="测试标题",
        content="这是一段测试内容，用于验证LLM接口是否正常连通。",
    )
    rewriter = RewriteProcessor(cfg)

    async def do_rewrite():
        await rewriter.__aenter__()
        try:
            result = await rewriter.rewrite(content)
            return result
        finally:
            await rewriter.__aexit__(None, None, None)

    result = asyncio.run(do_rewrite())
    ok = result.success
    return ok, 'success=' + str(result.success)


# ── 5. SEO Processor (async) ─────────────────────────────────
def test_seo_processor():
    from content_aggregator.processors.seo import SEOProcessor
    from content_aggregator.models import Content
    import yaml

    with open('config/config.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    content = Content(
        id="seo_test_001",
        source_id="rss",
        source_type="rss",
        url="https://example.com/ai-software",
        title="人工智能改变软件开发行业",
        content="人工智能正在深刻改变软件开发行业格局。大模型技术使自然语言处理能力大幅提升。",
    )

    async def do_seo():
        async with SEOProcessor(cfg) as seo_proc:
            result = await seo_proc.optimize(content)
            return result

    result = asyncio.run(do_seo())
    ok = result.success
    return ok, 'success=' + str(result.success)


# ── 6. 敏感词过滤 ────────────────────────────────────
def test_sensitive_filter():
    from content_aggregator.processors.filter.sensitive import SensitiveFilter, SensitiveFilterConfig

    config = SensitiveFilterConfig()
    f = SensitiveFilter(config)
    text = "这是一个正常的内容文本，不包含任何敏感词汇。"
    result = f.process(text)
    ok = isinstance(result, dict)
    return ok, "result_type=" + type(result).__name__


# ── 7. SimHash 去重 (async) ─────────────────────────────────
def test_dedup():
    from content_aggregator.processors.filter.dedup import DedupFilter, DedupFilterConfig

    config = DedupFilterConfig()
    dedup = DedupFilter(config)

    t1 = "人工智能正在改变世界，科技让生活更美好。"
    t2 = "人工智能正在改变世界，科技让生活更美好。"
    t3 = "今天的天气非常不错，阳光明媚，适合出行。"

    async def do_dedup():
        r1 = await dedup.process({"title": "文章A", "content": t1})
        r2 = await dedup.process({"title": "文章B", "content": t2})
        r3 = await dedup.process({"title": "文章C", "content": t3})
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(do_dedup())
    ok = (r1.get("success") and r2.get("success") and r3.get("success"))
    msg = "hash=" + str(r1.get("hash", ""))[:20] if ok else str(r1)[:50]
    return ok, msg


# ── 8. 全 Exporter 输出 ────────────────────────────────
def test_all_exporters():
    from content_aggregator.models import Article
    import yaml
    import os as _os

    with open('config/config.yaml', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    # Article 字段: id, title, original_title, source, source_url,
    #               author, published_at, content, summary, tags, word_count, metadata
    article = Article(
        id="test_001",
        source="RSS",
        source_url="https://example.com/rss",
        title="人工智能改变软件开发行业格局",
        content="人工智能正在深刻改变软件开发行业格局。大模型技术的突破使得自然语言处理能力大幅提升，人机交互更加自然流畅。未来已来，软件开发进入AI辅助时代。",
        author="测试作者",
        summary="本文探讨人工智能对软件开发行业的影响。",
        word_count=100,
        tags=["AI", "软件"],
        metadata={"source_id": "test_001"},
    )

    out_dir = _os.path.join(tempfile.gettempdir(), 'e2e_test')
    _os.makedirs(out_dir, exist_ok=True)

    # 各 exporter: __init__(output_dir: str), export(article, filename=path)
    exporter_specs = [
        ("PDF",
         _os.path.join(out_dir, 'test.pdf'),
         lambda: __import__('content_aggregator.exporters.pdf_exporter', fromlist=['PDFExporter']).PDFExporter(cfg),
         "output_path"),
        ("HTML",
         _os.path.join(out_dir, 'test.html'),
         lambda: __import__('content_aggregator.exporters.html.exporter', fromlist=['HTMLExporter']).HTMLExporter(out_dir),
         "filename"),
        ("JSON",
         _os.path.join(out_dir, 'test.json'),
         lambda: __import__('content_aggregator.exporters.json.exporter', fromlist=['JSONExporter']).JSONExporter(out_dir),
         "filename"),
        ("TXT",
         _os.path.join(out_dir, 'test.txt'),
         lambda: __import__('content_aggregator.exporters.txt', fromlist=['TXTExporter']).TXTExporter(out_dir),
         "filename"),
        ("Markdown",
         _os.path.join(out_dir, 'test.md'),
         lambda: __import__('content_aggregator.exporters.markdown.exporter', fromlist=['MarkdownExporter']).MarkdownExporter(out_dir),
         "filename"),
        ("Xiaohongshu",
         _os.path.join(out_dir, 'test_xhs.md'),
         lambda: __import__('content_aggregator.exporters.xiaohongshu.exporter', fromlist=['XiaohongshuExporter']).XiaohongshuExporter(out_dir),
         "filename"),
    ]

    results = []
    for name, path, make_exp, param_name in exporter_specs:
        try:
            exp = make_exp()
            if param_name == "output_path":
                exp.export(article, output_path=path)
            else:
                exp.export(article, filename=path)
            file_size = _os.path.getsize(path) if _os.path.exists(path) else 0
            results.append((name, True, file_size))
        except Exception as e:
            results.append((name, False, str(e)))

    all_ok = True
    for name, ok, size in results:
        icon = "[PASS]" if ok else "[FAIL]"
        print("    " + icon + " " + name + ": " + str(size))
        if not ok:
            all_ok = False

    return all_ok, ""


# ── Run ──────────────────────────────────────────────
if __name__ == "__main__":
    print("")
    print("=== content-aggregator 全流程测试 ===")
    print("")

    tests = [
        ("模块导入",         test_imports),
        ("PDF 中文字体注册", test_pdf_chinese_font),
        ("RSS 采集",         test_rss_collect),
        ("LLM Rewriter",    test_rewriter),
        ("SEO Processor",   test_seo_processor),
        ("敏感词过滤",       test_sensitive_filter),
        ("SimHash 去重",    test_dedup),
        ("全 Exporter 输出", test_all_exporters),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print("[" + name + "]")
        if run_test(name, fn):
            passed += 1
        else:
            failed += 1
        print("")

    print("=== 结果: " + str(passed) + " 通过, " + str(failed) + " 失败 ===")
