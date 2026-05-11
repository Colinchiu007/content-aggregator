"""
End-to-end pipeline test

RSS -> LLM Rewrite -> Export
"""

import sys
sys.path.insert(0, "src")

import asyncio
import uuid
from datetime import datetime

from content_aggregator.sources.rss import RSSCollector
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteStrategy
from content_aggregator.exporters import Exporter


def test_pipeline():
    """Test full pipeline: RSS -> LLM Rewrite -> Export"""
    print("=" * 60)
    print("End-to-End Pipeline Test")
    print("=" * 60)

    # Step 1: RSS Collection
    print("\n[Step 1] RSS Collection...")
    collector = RSSCollector(
        url="https://www.ruanyifeng.com/blog/atom.xml",
        name="阮一峰博客",
        max_items=1
    )
    result = collector.collect()
    articles = result.get("data", []) if isinstance(result, dict) else result
    print(f"  Collected: {len(articles)} articles")
    
    if not articles:
        print("  [FAIL] No articles collected")
        return
    
    article = articles[0]
    print(f"  Title: {article.title}")
    print(f"  URL: {article.url}")
    print(f"  Content: {article.content[:200]}...")

    # Step 2: LLM Rewrite
    print("\n[Step 2] LLM Rewrite...")
    
    # Try to load from yaml config
    import os
    import yaml
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        # Load from config.yaml
        config_path = "config/config.yaml"
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
                api_key = config_data.get("llm", {}).get("api_key", "")
    
    if not api_key:
        print("  [SKIP] No API key")
        rewritten = article.content
    else:
        # Create config dict
        llm_config = {
            "provider": "deepseek",
            "api_key": api_key,
            "model": "deepseek-chat"
        }
        processor = RewriteProcessor(config=llm_config)
        
        # Import Content and RewriteConfig
        from content_aggregator.models import Content as ContentModel
        from content_aggregator.processors.rewrite.rewriter import RewriteConfig, RewriteStrategy
        
        # Create Content object (import aliased to avoid conflict with Content from sources)
        content_obj = ContentModel(
            id=str(uuid.uuid4()),
            source_id="rss_ruanyifeng",
            source_type="rss",
            url=article.url,
            title=article.title,
            content=article.content[:3000]  # Limit for API
        )
        
        # Create RewriteConfig
        rewrite_cfg = RewriteConfig(strategy=RewriteStrategy.REWRITE)
        
        # Run rewrite
        result = asyncio.run(processor.rewrite(content_obj, rewrite_cfg))
        
        if result.success:
            print(f"  [OK] Rewritten: {len(result.rewritten_content)} chars")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Tokens: {result.metadata.get('tokens_used', 'N/A')}")
            rewritten = result.rewritten_content
        else:
            print(f"  [FAIL] {result.error}")
            rewritten = article.content

    # Step 3: Export
    print("\n[Step 3] Export...")
    
    # Update article with rewritten content
    article.content = rewritten
    
    exporter = Exporter("./output/exports")
    paths = exporter.export_batch([article], ["markdown", "html", "json"])
    
    print(f"  Exported: {len(paths)} files")
    for p in paths:
        print(f"  - {p}")

    print("\n" + "=" * 60)
    print("Pipeline test completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_pipeline()