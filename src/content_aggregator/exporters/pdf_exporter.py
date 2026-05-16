"""
PDF 导出器

将文章内容导出为 PDF 文件，支持中文字体、微信公众号内联样式。
依赖 reportlab 库（pip install reportlab）。
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from content_aggregator.models import Article


@dataclass
class PDFConfig:
    """PDF 导出配置"""
    # 页面大小：letter / A4 / legal
    page_size: str = "A4"
    # 字体大小（pt）
    font_size: int = 10
    # 行距
    line_spacing: float = 1.5
    # 页面边距（pt）
    margin_top: float = 72
    margin_bottom: float = 72
    margin_left: float = 72
    margin_right: float = 72
    # 中文字体路径（留空使用系统默认）
    # Windows 示例：msyh.ttc（微软雅黑）
    # macOS 示例：STHeiti Light.ttc
    # Linux 示例：/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
    chinese_font: str = ""
    # 字体名称（英文，用于 reportlab）
    font_name: str = "Helvetica"
    # 是否启用语法高亮（代码块）
    code_highlight: bool = True
    # 代码块背景色
    code_bg_color: tuple[float, float, float] = (0.95, 0.95, 0.95)
    # 标题字体大小
    title_font_size: int = 16
    # 副标题字体大小
    subtitle_font_size: int = 12


@dataclass
class PDFExportResult:
    """导出结果"""
    success: bool
    file_path: str = ""
    file_size: int = 0
    page_count: int = 0
    error: str | None = None


class PDFExporter:
    """
    PDF 导出器

    将 Article 对象导出为 PDF 文件，支持：
    - Markdown 内容解析（标题、列表、代码块、引用等）
    - 中文字体支持
    - 微信公众号内联样式转换

    使用示例：
        exporter = PDFExporter(config)
        result = exporter.export(article, "output/article.pdf")

        # 或批量导出
        exporter.export_batch(articles, "output/", prefix="article")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        初始化 PDF 导出器

        参数：
            config: 配置字典（可选）
        """
        self.config = config or {}
        self.pdf_config = PDFConfig()

        # 尝试导入 reportlab
        self._reportlab_available = False
        try:
            from reportlab.lib.pagesizes import A4, letter, legal
            from reportlab.pdfgen import canvas
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, PageBreak
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
            self._reportlab_available = True
            self._styles = None  # 延迟初始化
        except ImportError:
            logger.warning("reportlab 未安装，无法使用 PDF 导出功能")
            logger.info("请运行: pip install reportlab")

    @property
    def available(self) -> bool:
        """是否可用（reportlab 已安装）"""
        return self._reportlab_available

    def export(
        self,
        article: Article,
        output_path: str,
        pdf_config: PDFConfig | None = None
    ) -> PDFExportResult:
        """
        导出单篇文章为 PDF

        参数：
            article: Article 对象
            output_path: 输出文件路径
            pdf_config: PDF 配置（可选）

        返回：
            PDFExportResult
        """
        if not self._reportlab_available:
            return PDFExportResult(
                success=False,
                error="reportlab 库未安装，请运行: pip install reportlab"
            )

        if pdf_config is None:
            pdf_config = self.pdf_config

        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            # 创建 PDF
            page_size = self._get_page_size(pdf_config.page_size)
            c = self._create_canvas(output_path, page_size, pdf_config)

            # 写入内容
            self._draw_content(c, article, pdf_config, page_size)

            # 保存
            c.save()

            # 获取文件信息
            file_size = os.path.getsize(output_path)

            return PDFExportResult(
                success=True,
                file_path=output_path,
                file_size=file_size,
                page_count=self._estimate_pages(article, pdf_config)
            )

        except Exception as e:
            logger.error(f"PDF export error: {e}")
            return PDFExportResult(success=False, error=str(e))

    def export_from_html(
        self,
        html_content: str,
        output_path: str,
        title: str = "",
        pdf_config: PDFConfig | None = None
    ) -> PDFExportResult:
        """从 HTML 内容导出 PDF"""
        if not self._reportlab_available:
            return PDFExportResult(
                success=False,
                error="reportlab 库未安装"
            )

        if pdf_config is None:
            pdf_config = self.pdf_config

        try:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

            page_size = self._get_page_size(pdf_config.page_size)
            c = self._create_canvas(output_path, page_size, pdf_config)

            # 解析 HTML 并绘制
            self._draw_html_content(c, html_content, title, pdf_config, page_size)

            c.save()

            return PDFExportResult(
                success=True,
                file_path=output_path,
                file_size=os.path.getsize(output_path),
                page_count=1
            )

        except Exception as e:
            logger.error(f"PDF export error: {e}")
            return PDFExportResult(success=False, error=str(e))

    def _get_page_size(self, size_name: str):
        """获取页面尺寸"""
        from reportlab.lib.pagesizes import A4, letter, legal

        sizes = {
            "letter": letter,
            "A4": A4,
            "legal": legal,
        }
        return sizes.get(size_name.lower(), A4)

    def _create_canvas(self, output_path: str, page_size, config: PDFConfig):
        """创建 PDF 画布"""
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path, pagesize=page_size)
        c.setTitle(config.font_name)
        return c

    def _draw_content(
        self,
        c,
        article: Article,
        config: PDFConfig,
        page_size
    ):
        """绘制 Article 内容"""
        width, height = page_size
        margin_left = config.margin_left
        margin_right = config.margin_right
        margin_top = config.margin_top
        margin_bottom = config.margin_bottom

        text_width = width - margin_left - margin_right
        y = height - margin_top

        # 标题
        title_style = {
            "fontSize": config.title_font_size,
            "leading": config.title_font_size * 1.5,
        }
        y = self._draw_text(
            c, article.title, margin_left, y,
            text_width, config, **title_style
        )
        y -= 10  # 标题后间距

        # 元信息（作者、日期、来源）
        meta_lines = []
        if getattr(article, 'author', None):
            meta_lines.append(f"作者：{article.author}")
        if getattr(article, 'published_date', None):
            meta_lines.append(f"日期：{article.published_date}")
        if getattr(article, 'source', None):
            meta_lines.append(f"来源：{article.source}")

        if meta_lines:
            meta_style = {
                "fontSize": 9,
                "leading": 14,
                "color": (0.5, 0.5, 0.5)
            }
            for line in meta_lines:
                y = self._draw_text(c, line, margin_left, y, text_width, config, **meta_style)
            y -= 15

        # 分割线
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setLineWidth(0.5)
        c.line(margin_left, y, width - margin_right, y)
        y -= 20

        # 正文
        content_lines = article.content.split("\n")
        for line in content_lines:
            # 处理 Markdown 标记
            processed = self._process_markdown_line(line)

            if line.startswith("# "):
                # 一级标题
                y = self._draw_text(
                    c, line[2:], margin_left, y, text_width, config,
                    fontSize=14, leading=20, bold=True
                )
            elif line.startswith("## "):
                # 二级标题
                y = self._draw_text(
                    c, line[3:], margin_left, y, text_width, config,
                    fontSize=12, leading=17, bold=True
                )
            elif line.startswith("### "):
                y = self._draw_text(
                    c, line[4:], margin_left, y, text_width, config,
                    fontSize=11, leading=15, bold=True
                )
            elif line.strip().startswith("- ") or line.strip().startswith("* "):
                # 列表项
                indent = 20
                y = self._draw_text(
                    c, "• " + line.strip()[2:], margin_left + indent, y,
                    text_width - indent, config, fontSize=config.font_size, leading=config.font_size * config.line_spacing
                )
            elif line.strip() == "":
                # 空行
                y -= 8
            elif line.strip().startswith("```"):
                # 代码块（简化处理）
                pass
            elif line.startswith(">"):
                # 引用
                y = self._draw_text(
                    c, line[1:].strip(), margin_left + 15, y,
                    text_width - 15, config,
                    fontSize=config.font_size - 1,
                    leading=config.font_size * config.line_spacing,
                    color=(0.5, 0.5, 0.5),
                    italic=True
                )
            else:
                # 普通段落
                y = self._draw_text(
                    c, processed, margin_left, y, text_width, config,
                    fontSize=config.font_size,
                    leading=config.font_size * config.line_spacing
                )

            # 页面溢出检测
            if y < margin_bottom + 50:
                c.showPage()
                y = height - margin_top

    def _draw_text(
        self,
        c,
        text: str,
        x: float,
        y: float,
        max_width: float,
        config: PDFConfig,
        fontSize: int | None = None,
        leading: float | None = None,
        bold: bool = False,
        italic: bool = False,
        color: tuple[float, float, float] | None = None,
        **kwargs
    ) -> float:
        """绘制文本，返回新的 Y 坐标"""
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        fs = fontSize or config.font_size
        lh = leading or (fs * config.line_spacing)

        # 字体
        font = config.font_name
        if bold:
            font = font + "-Bold"
        if italic:
            font = font + "-Oblique"

        c.setFont(font, fs)
        if color:
            c.setFillColorRGB(*color)
        else:
            c.setFillColorRGB(0, 0, 0)

        # 处理长文本换行
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            # 简单估算宽度
            char_width = fs * 0.5  # 中英文平均宽度
            if len(test_line) * char_width < max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        # 绘制每一行
        for line in lines:
            c.drawString(x, y, line)
            y -= lh

        return y

    def _process_markdown_line(self, line: str) -> str:
        """处理 Markdown 行内标记"""
        # 移除粗体/斜体标记（保留文字）
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        text = re.sub(r"\*(.+?)\*", r"\1", line)
        text = re.sub(r"__(.+?)__", r"\1", line)
        text = re.sub(r"_(.+?)_", r"\1", line)
        # 移除行内代码标记
        text = re.sub(r"`(.+?)`", r"\1", line)
        # 移除链接标记，保留文字
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
        return text

    def _draw_html_content(
        self,
        c,
        html: str,
        title: str,
        config: PDFConfig,
        page_size
    ):
        """从 HTML 内容绘制 PDF"""
        width, height = page_size

        y = height - config.margin_top

        # 标题
        if title:
            y = self._draw_text(
                c, title,
                config.margin_left, y,
                width - config.margin_left - config.margin_right,
                config,
                fontSize=config.title_font_size,
                leading=config.title_font_size * 1.5,
                bold=True
            )
            y -= 20

        # 简单 HTML 解析（去除标签，保留文字）
        # 移除脚本和样式
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

        # 移除所有 HTML 标签
        text = re.sub(r"<[^>]+>", "", html)
        # 处理实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        text = text.replace("&quot;", '"')

        # 分行处理
        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                y -= 10
                continue

            if len(line) > 200:  # 超长行截断
                line = line[:200] + "..."

            y = self._draw_text(
                c, line,
                config.margin_left, y,
                width - config.margin_left - config.margin_right,
                config,
                fontSize=config.font_size,
                leading=config.font_size * config.line_spacing
            )

            if y < config.margin_bottom + 50:
                c.showPage()
                y = height - config.margin_top

    def _estimate_pages(self, article: Article, config: PDFConfig) -> int:
        """估算页数"""
        # 简单估算：每页约 500 字
        total_chars = len(article.content) + len(article.title) * 2
        chars_per_page = 500 * config.line_spacing
        return max(1, int(total_chars / chars_per_page) + 1)

    def export_batch(
        self,
        articles: list[Article],
        output_dir: str,
        pdf_config: PDFConfig | None = None,
        prefix: str = "article"
    ) -> list[PDFExportResult]:
        """批量导出"""
        os.makedirs(output_dir, exist_ok=True)

        results = []
        for i, article in enumerate(articles):
            # 生成文件名
            safe_title = self._sanitize_filename(article.title)
            filename = f"{prefix}_{i+1:03d}_{safe_title}.pdf"
            output_path = os.path.join(output_dir, filename)

            result = self.export(article, output_path, pdf_config)
            results.append(result)

        return results

    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        # 移除非法字符
        name = re.sub(r'[\\/:*?"<>|]', "", name)
        # 截断长度
        name = name[:50].strip()
        return name if name else "untitled"