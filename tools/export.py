#!/usr/bin/env python
"""Content Export Tool - OpenClaw Wrapper"""
import sys
import os
import json
import yaml
from pathlib import Path

from content_aggregator.exporters.markdown.exporter import MarkdownExporter
from content_aggregator.exporters.html.exporter import HTMLExporter
from content_aggregator.exporters.json.exporter import JSONExporter
from content_aggregator.exporters.txt import TXTExporter
from content_aggregator.exporters.xiaohongshu.exporter import XiaohongshuExporter
from content_aggregator.exporters.pdf_exporter import PDFExporter
from content_aggregator.models import Content
from content_aggregator.processors.rewrite import RewriteResult


EXPORTER_MAP = {
    "markdown": MarkdownExporter,
    "html": HTMLExporter,
    "json": JSONExporter,
    "txt": TXTExporter,
    "xhs": XiaohongshuExporter,
    "pdf": PDFExporter,
}


def export_content(
    title: str,
    content: str,
    rewritten_title: str = None,
    rewritten_content: str = None,
    formats: list = None,
    output_dir: str = None,
    config_path: str = None
) -> dict:
    """
    Export content to specified formats.
    
    Args:
        title: Original title
        content: Original content
        rewritten_title: Rewritten title (optional)
        rewritten_content: Rewritten content (optional)
        formats: List of formats to export (markdown, html, json, txt, xhs)
        output_dir: Output directory (optional)
        config_path: Path to config file (optional)
    
    Returns:
        dict with keys: success, files (list of paths), error
    """
    if formats is None:
        formats = ["markdown"]
    
    # Load config for output_dir
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config" / "config.yaml")
    
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if output_dir is None:
        output_dir = config.get("export", {}).get("output_dir", "./output/exports")
    
    # Create Content and RewriteResult objects
    content_obj = Content(
        id="tool-export",
        source_id="manual",
        source_type="tool",
        title=title,
        content=content,
    )
    
    rewrite_result = None
    if rewritten_title or rewritten_content:
        rewrite_result = RewriteResult(
            original_title=title,
            original_content=content,
            rewritten_title=rewritten_title or title,
            rewritten_content=rewritten_content or content,
            strategy="TOOL",
            success=True,
        )
    
    # Export
    exported_files = []
    errors = []
    
    for fmt in formats:
        if fmt not in EXPORTER_MAP:
            errors.append(f"Unknown format: {fmt}")
            continue
        
        try:
            exporter_class = EXPORTER_MAP[fmt]
            exporter = exporter_class(config)
            
            if rewrite_result:
                filepath = exporter.export(rewrite_result, output_dir)
            else:
                filepath = exporter.export(content_obj, output_dir)
            
            exported_files.append(str(filepath))
        except Exception as e:
            errors.append(f"Export {fmt} failed: {e}")
    
    return {
        "success": len(errors) == 0,
        "files": exported_files,
        "error": "; ".join(errors) if errors else None,
    }


def main():
    """CLI interface"""
    if len(sys.argv) < 3:
        print("Usage: python -m tools.export <title> <content_file> [formats] [config_path]")
        print("  formats: comma-separated list (markdown,html,json,txt,xhs)")
        sys.exit(1)
    
    title = sys.argv[1]
    content_file = sys.argv[2]
    formats = sys.argv[3].split(",") if len(sys.argv) > 3 else ["markdown"]
    config_path = sys.argv[4] if len(sys.argv) > 4 else None
    
    with open(content_file, encoding="utf-8") as f:
        content = f.read()
    
    result = export_content(title, content, None, None, formats, None, config_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
