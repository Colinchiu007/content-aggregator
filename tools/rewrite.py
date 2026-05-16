#!/usr/bin/env python
"""Content Rewrite Tool - OpenClaw Wrapper"""
import sys
import os
import asyncio
import json
import yaml
from pathlib import Path

from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig
from content_aggregator.models import Content


def rewrite_content(
    title: str,
    content: str,
    source_url: str = "",
    strategy: str = "REWRITE",
    config_path: str = None
) -> dict:
    """
    Rewrite content using LLM.
    
    Args:
        title: Article title
        content: Article content
        source_url: Source URL (optional)
        strategy: Rewrite strategy (SUMMARIZE|STYLE_TRANSFER|PARAPHRASE|REWRITE|EXPAND|SHORT_VIDEO)
        config_path: Path to config file (optional)
    
    Returns:
        dict with keys: success, rewritten (title, content, strategy), error
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
        id="tool-rewrite",
        source_id=source_url or "manual",
        source_type="tool",
        title=title,
        content=content,
    )
    
    # Rewrite
    async def _rewrite():
        async with RewriteProcessor(config) as rewriter:
            return await rewriter.rewrite(content_obj, strategy)
    
    try:
        result = asyncio.run(_rewrite())
        return {
            "success": result.success,
            "rewritten": {
                "title": result.rewritten_title,
                "content": result.rewritten_content,
                "strategy": result.strategy,
            },
            "error": result.error,
        }
    except Exception as e:
        return {
            "success": False,
            "rewritten": None,
            "error": str(e),
        }


def main():
    """CLI interface"""
    if len(sys.argv) < 3:
        print("Usage: python -m tools.rewrite <title> <content_file> [strategy] [config_path]")
        print("  strategy: SUMMARIZE|STYLE_TRANSFER|PARAPHRASE|REWRITE|EXPAND|SHORT_VIDEO")
        sys.exit(1)
    
    title = sys.argv[1]
    content_file = sys.argv[2]
    strategy = sys.argv[3] if len(sys.argv) > 3 else "REWRITE"
    config_path = sys.argv[4] if len(sys.argv) > 4 else None
    
    with open(content_file, encoding="utf-8") as f:
        content = f.read()
    
    result = rewrite_content(title, content, "", strategy, config_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
