"""
内容格式化模块
- Markdown → 微信HTML / 其他平台格式
- 多格式导出
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from content_aggregator.models import Article


# ========================================================================
# 导出器模块
# ========================================================================

def markdown_to_html_inline(md_text: str) -> str:
    """
    将 Markdown 转换为内联样式 HTML
    兼容微信公众号渲染
    """
    html = md_text

    # 代码块
    html = re.sub(
        r'```(\w*)\n(.*?)```',
        lambda m: f'<pre style="background:#f5f5f5;padding:16px;border-radius:4px;font-family:monospace;font-size:14px;overflow-x:auto;"><code>{_escape_html(m.group(2))}</code></pre>',
        html,
        flags=re.DOTALL,
    )

    # 行内代码
    html = re.sub(
        r'`([^`]+)`',
        lambda m: f'<code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-family:monospace;font-size:14px;color:#c7254e;">{_escape_html(m.group(1))}</code>',
        html,
    )

    # 引用块
    html = re.sub(
        r'^>\s*(.+)$',
        lambda m: f'<blockquote style="margin:1em 0;padding:12px 16px;background:#f7f7f7;border-left:4px solid #ddd;color:#666;font-size:15px;">{m.group(1)}</blockquote>',
        html,
        flags=re.MULTILINE,
    )

    # 标题
    html = re.sub(r'^###\s+(.+)$', lambda m: f'<h3 style="font-size:16px;font-weight:bold;color:#333;margin:1.2em 0 0.6em;">{m.group(1)}</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^##\s+(.+)$', lambda m: f'<h2 style="font-size:18px;font-weight:bold;color:#1a1a1a;margin:1.5em 0 0.8em;padding-bottom:0.3em;border-bottom:2px solid #e8e8e8;">{m.group(1)}</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^#\s+(.+)$', lambda m: f'<h1 style="font-size:20px;font-weight:bold;color:#1a1a1a;margin:1.5em 0 0.8em;">{m.group(1)}</h1>', html, flags=re.MULTILINE)

    # 粗体和斜体
    html = re.sub(r'\*\*(.+?)\*\*', lambda m: f'<strong style="font-weight:bold;color:#1a1a1a;">{m.group(1)}</strong>', html)
    html = re.sub(r'\*(.+?)\*', lambda m: f'<em>{m.group(1)}</em>', html)

    # 链接
    html = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        lambda m: f'<a href="{m.group(2)}" style="color:#576b95;text-decoration:none;">{m.group(1)}</a>',
        html,
    )

    # 无序列表
    html = re.sub(r'^[-*]\s+(.+)$', lambda m: f'<li style="margin-bottom:0.5em;line-height:1.8;">• {m.group(1)}</li>', html, flags=re.MULTILINE)

    # 有序列表
    html = re.sub(r'^\d+\.\s+(.+)$', lambda m: f'<li style="margin-bottom:0.5em;line-height:1.8;">{m.group(1)}</li>', html, flags=re.MULTILINE)

    # 段落
    lines = html.split('\n')
    processed_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            processed_lines.append('')
        elif stripped.startswith('<'):
            processed_lines.append(stripped)
        else:
            processed_lines.append(f'<p style="margin-bottom:1.2em;text-align:justify;">{stripped}</p>')

    html = '\n'.join(processed_lines)

    # 清理多余空行
    html = re.sub(r'\n{3,}', '\n\n', html)

    return html


def markdown_to_wechat_html(md_text: str, images: list[dict] | None = None) -> str:
    """
    将 Markdown 转换为公众号 HTML（带模板包裹）
    images: [{path, position, url}]
    """
    inner_html = markdown_to_html_inline(md_text)

    # 插入图片
    if images:
        img_idx = 0
        para_count = 0
        result_lines = []
        for line in inner_html.split('\n'):
            result_lines.append(line)
            if '<p ' in line or '<h' in line:
                para_count += 1
                while img_idx < len(images) and images[img_idx].get("position") == para_count:
                    img = images[img_idx]
                    src = img.get("url", img.get("path", ""))
                    alt = img.get("alt", "")
                    result_lines.append(f'<img src="{src}" alt="{alt}" style="max-width:100%;height:auto;display:block;margin:1em auto;border-radius:4px;" />')
                    img_idx += 1
        inner_html = '\n'.join(result_lines)

    # 包裹在模板中
    template = """
<div style="max-width:677px;margin:0 auto;padding:20px 16px;font-family:-apple-system,BlinkMacSystemFont,'Helvetica Neue','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;font-size:16px;line-height:1.8;color:#333;word-wrap:break-word;">
{content}
</div>
"""
    return template.format(content=inner_html)


def _escape_html(text: str) -> str:
    """HTML 转义"""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


class ContentFormatter:
    """内容格式化器"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.default_format = self.config.get("default_format", "markdown")

    async def format_article(self, article: "Article", format_type: str = None) -> dict:
        """
        格式化文章

        参数：
            article: Article 对象
            format_type: 格式类型（markdown/html/json/txt）

        返回：
            格式化后的数据字典
        """
        if format_type is None:
            format_type = self.default_format

        result = {
            "id": article.id,
            "title": article.title,
            "format": format_type,
        }

        if format_type == "html" or format_type == "wechat":
            result["content"] = markdown_to_wechat_html(article.content)
            result["content_type"] = "text/html"
        elif format_type == "json":
            result["content"] = self._to_json(article)
            result["content_type"] = "application/json"
        elif format_type == "txt":
            result["content"] = article.content
            result["content_type"] = "text/plain"
        else:  # markdown (default)
            result["content"] = self._to_markdown(article)
            result["content_type"] = "text/markdown"

        return result

    def _to_markdown(self, article: "Article") -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"# {article.title}",
            "",
        ]

        # 元数据
        if article.author:
            lines.append(f"**作者**: {article.author}")
        if article.source:
            lines.append(f"**来源**: {article.source}")
        if article.tags:
            lines.append(f"**标签**: {', '.join(article.tags)}")
        lines.append("")

        # 正文
        lines.append(article.content)

        return "\n".join(lines)

    def _to_json(self, article: "Article") -> str:
        """转换为 JSON 格式"""
        import json
        return json.dumps(article.to_dict(), ensure_ascii=False, indent=2)

    async def export_file(self, article: "Article", output_dir: str, format_type: str = None) -> str:
        """
        导出文章到文件

        参数：
            article: Article 对象
            output_dir: 输出目录
            format_type: 格式类型

        返回：
            文件路径
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if format_type is None:
            format_type = self.default_format

        # 文件扩展名
        ext_map = {
            "markdown": "md",
            "html": "html",
            "wechat": "html",
            "json": "json",
            "txt": "txt",
        }
        ext = ext_map.get(format_type, "md")

        # 文件名
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', article.title)[:50]
        filename = f"{safe_title}_{article.id[:8]}.{ext}"
        filepath = Path(output_dir) / filename

        # 格式化内容
        formatted = await self.format_article(article, format_type)
        content = formatted["content"]

        # 写入文件
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Exported: {filepath}")

        return str(filepath)


# 兼容旧接口
class MarkdownExporter:
    """Markdown 导出器（兼容旧接口）"""

    @staticmethod
    def export(article, output_dir):
        """导出为 Markdown 文件"""
        formatter = ContentFormatter()
        return formatter.export_file(article, output_dir, "markdown")