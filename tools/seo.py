#!/usr/bin/env python
"""SEO Optimization Tool - OpenClaw Wrapper"""
import sys
import os
import asyncio
import json
import yaml
from pathlib import Path

from content_aggregator.processors.seo import SEOProcessor, SEOConfig
from content_aggregator.models import Content


def seo_optimize(
    title: str,
    content: str,
    source_url: str = "",
    config_path: str = None
) -> dict:
    """
    Perform SEO optimization on content.
    
    Args:
        title: Article title
        content: Article content
        source_url: Source URL (optional)
        config_path: Path to config file (optional)
    
    Returns:
        dict with keys: success, seo (keywords, description, title, tags), error
    """
    # Load config
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config" / "config.yaml")
    
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    # Set proxy if configured
    proxy_config = config.get("proxy", {})
    if proxy_config.get("enabled"):
        proxy_url = proxy_config.get("url")
        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
    
    # Create Content object
    content_obj = Content(
        id="tool-seo",
        source_id=source_url or "manual",
        source_type="tool",
        title=title,
        content=content,
    )
    
    # SEO optimize
    async def _optimize():
        seo_config = SEOConfig(**config.get("seo", {}))
        async with SEOProcessor(config) as processor:
            return await processor.optimize(content_obj, seo_config)
    
    try:
        result = asyncio.run(_optimize())
        return {
            "success": result.success,
            "seo": {
                "keywords": result.keywords,
                "description": result.meta_description,
                "title": result.meta_title,
                "tags": result.optimized_tags,
            },
            "duration": result.duration,
            "error": result.error,
        }
    except Exception as e:
        return {
            "success": False,
            "seo": None,
            "error": str(e),
        }


def main():
    """CLI interface"""
    if len(sys.argv) < 3:
        print("Usage: python -m tools.seo <title> <content_file> [config_path]")
        sys.exit(1)
    
    title = sys.argv[1]
    content_file = sys.argv[2]
    config_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    with open(content_file, encoding="utf-8") as f:
        content = f.read()
    
    result = seo_optimize(title, content, "", config_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
