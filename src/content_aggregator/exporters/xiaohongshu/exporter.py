"""
小红书文案导出器模块

将 Article 转换为小红书风格的文案格式，带 emoji 和话题标签。
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from content_aggregator.models import Article


def to_xiaohongshu(article: "Article") -> str:
    """
    将 Article 转换为小红书文案格式

    参数：
        article: Article 对象

    返回：
        小红书格式字符串
    """
    lines = []

    # 标题（带emoji）
    lines.append(f"✨ {article.title}\n")

    # 标签
    if article.tags:
        tags_line = " ".join([f"#{tag}" for tag in article.tags])
        lines.append(f"{tags_line}\n")
    else:
        # 自动生成标签
        lines.append("#内容分享 #干货分享\n")
    lines.append("---\n")

    # 正文（分段，带emoji）
    paragraphs = article.content.split('\n\n')
    emoji_list = ["📌", "💡", "🎯", "📝", "💪", "🌟", "🔥", "📊"]

    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue

        # 清理 Markdown 格式
        para = re.sub(r'#{1,6}\s+', '', para)  # 标题
        para = re.sub(r'\*\*(.+?)\*\*', r'\1', para)  # 粗体
        para = re.sub(r'\*(.+?)\*', r'\1', para)  # 斜体
        para = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', para)  # 链接
        para = re.sub(r'`([^`]+)`', r'\1', para)  # 代码

        # 添加 emoji
        emoji = emoji_list[i % len(emoji_list)]
        lines.append(f"{emoji} {para}\n")
        lines.append("")

    # 结尾
    lines.append("---\n")
    if article.source:
        lines.append(f"📖 来源: {article.source}")
    if article.url:
        lines.append(f"🔗 原文: {article.url}")

    return "\n".join(lines)


class XiaohongshuExporter:
    """
    小红书文案导出器

    使用示例：
        exporter = XiaohongshuExporter("./output")
        path = exporter.export(article)
    """

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", filename: str | None = None) -> str:
        """导出 Article 为小红书格式文件"""
        content = to_xiaohongshu(article)

        if filename is None:
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
            filename = f"{safe_title}_小红书.md"

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
                logger.error(f"Xiaohongshu export failed for {article.title}: {e}")
        return paths