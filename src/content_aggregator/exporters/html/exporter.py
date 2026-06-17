"""
HTML 导出器模块

将 Article 转换为 HTML 格式（微信内联样式），适合直接粘贴到公众号编辑器。
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from content_aggregator.models import Article


def markdown_to_wechat_html(markdown_text: str) -> str:
    """
    将 Markdown 转换为微信兼容的 HTML（内联样式）

    参数：
        markdown_text: Markdown 文本

    返回：
        带 CSS 内联样式的 HTML 字符串
    """
    # 基础样式配置
    styles = {
        "p": "margin: 0 0 16px 0; line-height: 1.75; font-size: 17px; color: #3f3f3f;",
        "h2": "margin: 24px 0 16px 0; font-size: 22px; font-weight: bold; color: #2b2b2b; border-left: 5px solid #555; padding-left: 10px;",
        "h3": "margin: 20px 0 12px 0; font-size: 19px; font-weight: bold; color: #2b2b2b;",
        "h4": "margin: 16px 0 8px 0; font-size: 17px; font-weight: bold; color: #3f3f3f;",
        "blockquote": "margin: 16px 0; padding: 12px 16px; background: #f7f7f7; border-left: 4px solid #ddd; color: #666; font-size: 15px;",
        "code": "background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 15px; color: #c7254e;",
        "pre": "margin: 16px 0; padding: 16px; background: #282c34; border-radius: 6px; overflow-x: auto;",
        "pre_code": "color: #abb2bf; font-size: 14px; line-height: 1.5; font-family: 'Menlo', 'Monaco', monospace;",
        "ul": "margin: 0 0 16px 0; padding-left: 24px; line-height: 1.75;",
        "ol": "margin: 0 0 16px 0; padding-left: 24px; line-height: 1.75;",
        "li": "margin: 4px 0; font-size: 17px; color: #3f3f3f;",
        "a": "color: #576b95; text-decoration: none;",
        "img": "max-width: 100%; height: auto; margin: 16px 0; border-radius: 4px;",
        "strong": "font-weight: bold; color: #2b2b2b;",
        "em": "font-style: italic;",
    }

    html = markdown_text

    # 代码块 (```...```)
    html = re.sub(
        r'```(\w*)\n([\s\S]*?)```',
        lambda m: f'<pre style="{styles["pre"]}"><code style="{styles["pre_code"]}">{m.group(2).strip()}</code></pre>',
        html
    )

    # 行内代码 (`...`)
    html = re.sub(r'`([^`]+)`', f'<code style="{styles["code"]}">\\1</code>', html)

    # 标题
    html = re.sub(r'^#### (.+)$', f'<h4 style="{styles["h4"]}">\\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', f'<h3 style="{styles["h3"]}">\\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', f'<h2 style="{styles["h2"]}">\\1</h2>', html, flags=re.MULTILINE)

    # 粗体和斜体
    html = re.sub(r'\*\*(.+?)\*\*', f'<strong style="{styles["strong"]}">\\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', f'<em style="{styles["em"]}">\\1</em>', html)

    # 链接
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', f'<a href="\\2" style="{styles["a"]}">\\1</a>', html)

    # 引用块
    html = re.sub(r'^> (.+)$', f'<blockquote style="{styles["blockquote"]}">\\1</blockquote>', html, flags=re.MULTILINE)

    # 无序列表
    html = re.sub(r'^- (.+)$', f'<li style="{styles["li"]}">\\1</li>', html, flags=re.MULTILINE)

    # 有序列表
    html = re.sub(r'^\d+\. (.+)$', f'<li style="{styles["li"]}">\\1</li>', html, flags=re.MULTILINE)

    # 段落（非空行且不在其他标签内）
    lines = html.split('\n')
    processed_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed_lines.append('')
        elif stripped.startswith('<') and not stripped.startswith('<code'):
            processed_lines.append(stripped)
        else:
            processed_lines.append(f'<p style="{styles["p"]}">{stripped}</p>')

    html = '\n'.join(processed_lines)

    # 清理多余空行
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html.strip()


def to_html(article: "Article") -> str:
    """
    将 Article 转换为 HTML 格式

    参数：
        article: Article 对象

    返回：
        HTML 字符串
    """
    # 标题
    html = f'<h2 style="margin: 0 0 16px 0; font-size: 24px; font-weight: bold; color: #2b2b2b;">{article.title}</h2>\n\n'

    # 元数据
    meta_items = []
    if article.author:
        meta_items.append(f'<span style="color: #888; font-size: 14px;">作者: {article.author}</span>')
    if article.source:
        meta_items.append(f'<span style="color: #888; font-size: 14px;">来源: {article.source}</span>')
    if article.published_at:
        meta_items.append(f'<span style="color: #888; font-size: 14px;">日期: {article.published_at.strftime("%Y-%m-%d")}</span>')

    if meta_items:
        html += '<p style="margin: 0 0 16px 0; font-size: 14px; color: #888;">' + ' | '.join(meta_items) + '</p>\n\n'

    # 分隔线
    html += '<hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;">\n\n'

    # 正文
    html += markdown_to_wechat_html(article.content)

    return html


class HTMLExporter:
    """
    HTML 导出器

    使用示例：
        exporter = HTMLExporter("./output")
        path = exporter.export(article)
    """

    def __init__(self, output_dir: str = "./output/exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, article: "Article", filename: str | None = None) -> str:
        """导出 Article 为 HTML 文件"""
        content = to_html(article)

        if filename is None:
            import re
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
            filename = f"{safe_title}.html"

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
                logger.error(f"HTML export failed for {article.title}: {e}")
        return paths