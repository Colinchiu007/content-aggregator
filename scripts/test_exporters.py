"""
Exporter module test script

Test all exporters: markdown, html, json, xiaohongshu
"""

import sys
sys.path.insert(0, "src")

import uuid
from datetime import datetime

from content_aggregator.models import Article
from content_aggregator.exporters import Exporter


def test_exporters():
    """Test all exporters"""
    # Create test article
    article = Article(
        id=str(uuid.uuid4()),
        title="AI Development Trends",
        original_title="AI Development Trends",
        source="Tech Blog",
        source_url="https://example.com/ai-trends",
        author="Tech Writer",
        published_at=datetime.now(),
        content="""
## Introduction

Artificial Intelligence (AI) is rapidly changing our world. This article discusses the latest trends.

## Key Trends

1. **Large Language Models**: GPT, Claude, DeepSeek
2. **Multimodal AI**: Text, image, audio combined
3. **Edge AI**: Running AI on devices

## Conclusion

AI will continue to evolve. Stay updated!
        """.strip(),
        summary="AI trends summary",
        tags=["AI", "Technology", "Trends"],
    )

    print("=" * 60)
    print("Exporter Module Test")
    print("=" * 60)

    # Test individual exporters
    from content_aggregator.exporters.markdown import to_markdown
    from content_aggregator.exporters.html import to_html
    from content_aggregator.exporters.json import to_json
    from content_aggregator.exporters.xiaohongshu import to_xiaohongshu

    print("\n[1] Markdown Exporter...")
    md = to_markdown(article)
    print(f"  [OK] {len(md)} chars")
    print(f"  Preview: {md[:100]}...")

    print("\n[2] HTML Exporter...")
    html = to_html(article)
    print(f"  [OK] {len(html)} chars")
    print(f"  Preview: {html[:100]}...")

    print("\n[3] JSON Exporter...")
    json_str = to_json(article)
    print(f"  [OK] {len(json_str)} chars")

    print("\n[4] Xiaohongshu Exporter...")
    xhs = to_xiaohongshu(article)
    print(f"  [OK] {len(xhs)} chars")

    # Test unified exporter
    print("\n[5] Unified Exporter (file export)...")
    exporter = Exporter("./output/exports")
    paths = exporter.export_batch([article], ["markdown", "html", "json", "xiaohongshu"])
    print(f"  [OK] Exported {len(paths)} files")
    for p in paths:
        print(f"  - {p}")

    print("\n" + "=" * 60)
    print("All tests passed!")


if __name__ == "__main__":
    test_exporters()