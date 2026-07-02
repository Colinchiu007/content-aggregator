"""
导出器模块

提供多种格式的导出功能：Markdown、HTML、JSON、小红书。

使用示例：
    from content_aggregator.exporters import Exporter

    exporter = Exporter("./output")
    paths = exporter.export_batch(articles, ["markdown", "html"])
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from content_aggregator.exporters.markdown import to_markdown
from content_aggregator.exporters.html import to_html
from content_aggregator.exporters.json import to_json, to_json_compact
from content_aggregator.exporters.xiaohongshu import to_xiaohongshu
from content_aggregator.exporters.txt import to_txt
from content_aggregator.exporters.pdf_exporter import PDFExporter, PDFConfig, PDFExportResult

if TYPE_CHECKING:
    from content_aggregator.models import Article


class Exporter:
    """
    统一导出器

    使用示例：
        exporter = Exporter("./output")

        # 导出单个
        path = exporter.export(article, "markdown")

        # 批量导出
        paths = exporter.export_batch(articles, ["markdown", "html", "json"])
    """

    # 转换函数映射
    CONVERTERS = {
        "markdown": to_markdown,
        "md": to_markdown,
        "html": to_html,
        "wechat": to_html,
        "json": to_json,
        "json-compact": to_json_compact,
        "txt": to_txt,
        "xiaohongshu": to_xiaohongshu,
        "xhs": to_xiaohongshu,
        "pdf": None,  # 单独处理，使用 PDFExporter
    }

    # 扩展名映射
    EXT_MAP = {
        "markdown": "md",
        "md": "md",
        "html": "html",
        "wechat": "html",
        "json": "json",
        "json-compact": "json",
        "txt": "txt",
        "xiaohongshu": "md",
        "xhs": "md",
        "pdf": "pdf",
    }

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", format_type: str = "markdown") -> str:
        """
        导出单个文章

        参数：
            article: Article 对象
            format_type: 格式类型（markdown/md, html, json, txt, xiaohongshu/xhs, pdf）

        返回：
            文件路径
        """
        ext = self.EXT_MAP.get(format_type.lower(), "md")

        # PDF 格式单独处理
        if format_type.lower() == "pdf":
            from content_aggregator.exporters.pdf_exporter import PDFExporter
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
            filename = f"{safe_title}.pdf"
            filepath = self.output_dir / filename
            exporter = PDFExporter()
            result = exporter.export(article, str(filepath))
            if result.success:
                return result.file_path
            else:
                from loguru import logger
                logger.error(f"PDF export failed: {result.error}")
                raise RuntimeError(result.error)

        converter = self.CONVERTERS.get(format_type.lower(), to_markdown)
        content = converter(article)

        # 文件名
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
        filename = f"{safe_title}.{ext}"
        filepath = self.output_dir / filename

        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def export_batch(
        self,
        articles: list["Article"],
        format_types: list[str] | None = None
    ) -> list[str]:
        """
        批量导出

        参数：
            articles: Article 列表
            format_types: 格式类型列表，默认 ["markdown", "html", "json"]

        返回：
            文件路径列表
        """
        if format_types is None:
            format_types = ["markdown", "html", "json"]

        paths = []
        for article in articles:
            for fmt in format_types:
                try:
                    path = self.export(article, fmt)
                    paths.append(path)
                except Exception as e:
                    from loguru import logger
                    logger.error(f"Export failed for {article.title} ({fmt}): {e}")

        return paths

    def list_exports(self) -> list[dict]:
        """列出所有导出文件"""
        exports = []
        for f in self.output_dir.iterdir():
            if f.is_file():
                exports.append({
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                })
        return exports


__all__ = [
    "Exporter",
    "PDFExporter",
    "PDFConfig",
    "PDFExportResult",
    "to_markdown",
    "to_html",
    "to_json",
    "to_json_compact",
    "to_txt",
    "to_xiaohongshu",
]