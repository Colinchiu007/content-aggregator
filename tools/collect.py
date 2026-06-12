#!/usr/bin/env python
"""Content Collection Tool - OpenClaw Wrapper"""
import sys
import os
import asyncio
import json
import yaml
from pathlib import Path

from content_aggregator.sources.web import WebSource
from content_aggregator.sources.base import SourceConfig
from content_aggregator.models import Content


def collect_content(url: str, config_path: str = None) -> dict:
    """
    Collect content from a URL.
    
    Args:
        url: The URL to collect content from
        config_path: Path to config file (optional)
    
    Returns:
        dict with keys: success, content (id, title, body, source_url), error
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
    
    # Create SourceConfig
    source_config = SourceConfig(
        id="tool-collect",
        name="Tool URL Collector",
        source_type="web",
        config={"url": url}
    )
    
    # Create WebSource
    proxy_url = proxy_config.get("url") if proxy_config.get("enabled") else None
    web_source = WebSource(source_config, proxy=proxy_url)
    
    # Collect content
    try:
        result = asyncio.run(web_source.collect())
        if result["success"] and result["contents"]:
            content = result["contents"][0]
            return {
                "success": True,
                "content": {
                    "id": content.id,
                    "title": content.title,
                    "body": content.content,
                    "source_url": content.source_id,
                },
                "error": None,
            }
        else:
            return {
                "success": False,
                "content": None,
                "error": result.get("error", "No content collected"),
            }
    except Exception as e:
        return {
            "success": False,
            "content": None,
            "error": str(e),
        }


def main():
    """CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python -m tools.collect <url> [config_path]")
        sys.exit(1)
    
    url = sys.argv[1]
    config_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = collect_content(url, config_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
