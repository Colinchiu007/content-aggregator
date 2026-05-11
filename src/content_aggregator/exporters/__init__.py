"""
导出器模块
提供多种格式的导出功能
"""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from content_aggregator.models import Article


# ========================================================================
# 导出函数
# ========================================================================

def to_markdown(article: "Article") -> str:
    """
    导出为 Markdown 格式

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


def to_html(article: "Article") -> str:
    """
    导出为 HTML 格式（微信内联样式）

    返回：
        HTML 字符串
    """
    # 使用 formatter 的转换函数
    from content_aggregator.processors.formatter import markdown_to_wechat_html
    return markdown_to_wechat_html(article.content)


def to_json(article: "Article") -> str:
    """
    导出为 JSON 格式

    返回：
        JSON 字符串
    """
    return json.dumps(article.to_dict(), ensure_ascii=False, indent=2)


def to_json_compact(article: "Article") -> str:
    """
    导出为紧凑 JSON 格式（无缩进）

    返回：
        JSON 字符串
    """
    return json.dumps(article.to_dict(), ensure_ascii=False)


def to_txt(article: "Article") -> str:
    """
    导出为纯文本格式

    返回：
        纯文本字符串（无格式）
    """
    lines = [
        article.title,
        "",
        "=" * 50,
        "",
    ]

    # 元数据
    if article.author:
        lines.append(f"作者: {article.author}")
    if article.source:
        lines.append(f"来源: {article.source}")
    if article.tags:
        lines.append(f"标签: {', '.join(article.tags)}")
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


def to_xiaohongshu(article: "Article") -> str:
    """
    导出为小红书文案格式

    返回：
        小红书格式字符串（带emoji和话题标签）
    """
    lines = []

    # 标题（带emoji）
    lines.append(f"✨ {article.title}\n")

    # 标签
    if article.tags:
        tags_line = " ".join([f"#{tag}" for tag in article.tags])
        lines.append(f"{tags_line}\n")
    else:
        lines.append("#内容分享\n")
    lines.append("---\n")

    # 正文（分段，带emoji）
    paragraphs = article.content.split('\n\n')
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue

        # 添加 emoji
        if i == 0:
            lines.append(f"📌 {para}\n")
        elif i == 1:
            lines.append(f"💡 {para}\n")
        else:
            lines.append(f"{para}\n")

        lines.append("")

    # 结尾
    if article.source_url:
        lines.append("---\n")
        lines.append(f"📖 原文: {article.source_url}")

    return "\n".join(lines)


# ========================================================================
# 导出器类
# ========================================================================

class Exporter:
    """
    导出器

    使用示例：
        exporter = Exporter("./output")

        # 导出单个
        path = exporter.export(article, "markdown")

        # 批量导出
        paths = exporter.export_batch(articles, ["markdown", "html", "json"])
    """

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", format_type: str = "markdown") -> str:
        """
        导出单个文章

        参数：
            article: Article 对象
            format_type: 格式类型（markdown/html/json/txt/xiaohongshu）

        返回：
            文件路径
        """
        # 转换函数映射
        converters = {
            "markdown": to_markdown,
            "md": to_markdown,
            "html": to_html,
            "wechat": to_html,
            "json": to_json,
            "json-compact": to_json_compact,
            "txt": to_txt,
            "xiaohongshu": to_xiaohongshu,
            "xhs": to_xiaohongshu,
        }

        converter = converters.get(format_type.lower(), to_markdown)
        content = converter(article)

        # 扩展名
        ext_map = {
            "markdown": "md",
            "md": "md",
            "html": "html",
            "wechat": "html",
            "json": "json",
            "json-compact": "json",
            "txt": "txt",
            "xiaohongshu": "md",
            "xhs": "md",
        }
        ext = ext_map.get(format_type.lower(), "md")

        # 文件名
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
        filename = f"{safe_title}_{article.id[:8]}.{ext}"
        filepath = self.output_dir / filename

        # 写入
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def export_batch(self, articles: list["Article"], format_types: list[str] = None) -> list[str]:
        """
        批量导出

        参数：
            articles: Article 对象列表
            format_types: 格式类型列表，默认为 ["markdown", "html", "json"]

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