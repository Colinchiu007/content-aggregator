"""
TXT 导出器模块

将 Article 转换为纯文本格式（无格式标记）。
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from content_aggregator.models import Article


def to_txt(article: "Article") -> str:
    """
    将 Article 转换为纯文本格式

    参数：
        article: Article 对象

    返回：
        纯文本字符串
    """
    lines = [
        article.title,
        "",
        "=" * 50,
        "",
    ]

    # 元数据
    if article.author:
        lines.append(f"Author: {article.author}")
    if article.source:
        lines.append(f"Source: {article.source}")
    if article.tags:
        lines.append(f"Tags: {', '.join(article.tags)}")
    lines.append("")
    lines.append("=" * 50)
    lines.append("")

    # 正文（清理 Markdown 格式）
    content = article.content
    content = re.sub(r'#{1,6}\s+', '', content)  # 标题
    content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)  # 粗体
    content = re.sub(r'\*(.+?)\*', r'\1', content)  # 斜体
    content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)  # 链接
    content = re.sub(r'`([^`]+)`', r'\1', content)  # 代码
    content = re.sub(r'```[\s\S]*?```', '', content)  # 代码块

    lines.append(content)

    return "\n".join(lines)


class TXTExporter:
    """
    TXT 导出器

    使用示例：
        exporter = TXTExporter("./output")
        path = exporter.export(article)
    """

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", filename: str | None = None) -> str:
        """导出 Article 为 TXT 文件"""
        content = to_txt(article)

        if filename is None:
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
            filename = f"{safe_title}.txt"

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
                logger.error(f"TXT export failed for {article.title}: {e}")
        return paths