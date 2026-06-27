"""
JSON 导出器模块

将 Article 转换为 JSON 格式，支持美观格式和紧凑格式。
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from content_aggregator.models import Article


def to_json(article: "Article", indent: int = 2) -> str:
    """
    将 Article 转换为 JSON 格式

    参数：
        article: Article 对象
        indent: 缩进空格数，0 表示紧凑格式

    返回：
        JSON 字符串
    """
    return json.dumps(article.to_dict(), ensure_ascii=False, indent=indent if indent > 0 else None)


def to_json_compact(article: "Article") -> str:
    """紧凑 JSON 格式（无缩进）"""
    return to_json(article, indent=0)


class JSONExporter:
    """
    JSON 导出器

    使用示例：
        exporter = JSONExporter("./output")
        path = exporter.export(article)
    """

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", filename: str | None = None, indent: int = 2) -> str:
        """导出 Article 为 JSON 文件"""
        content = to_json(article, indent=indent)

        if filename is None:
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
            filename = f"{safe_title}.json"

        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")

        return str(filepath)

    def export_batch(self, articles: list["Article"], single_file: bool = False) -> list[str]:
        """
        批量导出

        参数：
            articles: Article 列表
            single_file: 是否合并为单个 JSON 文件

        返回：
            文件路径列表
        """
        if single_file:
            # 合并为单个文件
            data = [article.to_dict() for article in articles]
            filepath = self.output_dir / "articles.json"
            filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return [str(filepath)]
        else:
            # 每个文章单独文件
            paths = []
            for article in articles:
                try:
                    path = self.export(article)
                    paths.append(path)
                except Exception as e:
                    from loguru import logger
                    logger.error(f"JSON export failed for {article.title}: {e}")
            return paths