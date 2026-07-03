"""
Markdown 导出器模块

将 Article 转换为 Markdown 格式并导出为文件。
"""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from content_aggregator.models import Article


def to_markdown(article: "Article") -> str:
    """
    将 Article 转换为 Markdown 格式

    参数：
        article: Article 对象

    返回：
        Markdown 字符串
    """
    lines = [f"# {article.title}", ""]

    # 元数据
    if article.author:
        lines.append(f"**作者**: {article.author}")
    if article.source:
        lines.append(f"**来源**: {article.source}")
    if article.published_at:
        lines.append(f"**日期**: {article.published_at.strftime('%Y-%m-%d')}")
    if article.tags:
        lines.append(f"**标签**: {', '.join(article.tags)}")
    lines.append("")

    # 分隔线
    lines.append("---\n")

    # 正文
    lines.append(article.content)

    return "\n".join(lines)


class MarkdownExporter:
    """
    Markdown 导出器

    使用示例：
        exporter = MarkdownExporter("./output")
        path = exporter.export(article)
    """

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", filename: str | None = None) -> str:
        """
        导出 Article 为 Markdown 文件

        参数：
            article: Article 对象
            filename: 自定义文件名（可选）

        返回：
            文件路径
        """
        content = to_markdown(article)

        # 生成文件名
        if filename is None:
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
            filename = f"{safe_title}.md"

        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        return str(filepath)

    def export_batch(self, articles: list["Article"]) -> list[str]:
        """批量导出"""
        paths = []
        for article in articles:
            try:
                path = self.export(article)
                paths.append(path)
            except Exception as e:
                from loguru import logger
                logger.error(f"Markdown export failed for {article.title}: {e}")
        return paths