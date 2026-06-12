"""
测试导出器
"""

import pytest
import asyncio
import tempfile
from pathlib import Path

from content_aggregator.models import Content


class TestMarkdownExporter:
    """测试 Markdown 导出器"""
    
    @pytest.fixture
    def exporter(self):
        """创建 Markdown 导出器实例"""
        from content_aggregator.exporters.markdown.exporter import MarkdownExporter
        
        config = {"output_dir": "output"}
        return MarkdownExporter(config)
    
    @pytest.fixture
    def sample_content(self):
        """创建测试内容"""
        return Content(
            title="测试文章标题",
            content="# 这是一级标题\n\n这是正文内容。\n\n- 列表项1\n- 列表项2",
            url="https://example.com/test",
            source_id="test-source"
        )
    
    @pytest.mark.asyncio
    async def test_export_markdown(self, exporter, sample_content, tmp_path):
        """测试导出 Markdown 文件"""
        output_file = tmp_path / "test_output.md"
        
        # 调用导出方法
        result = await exporter.export(sample_content, str(output_file))
        
        # 验证文件已创建
        assert output_file.exists()
        
        # 验证内容正确
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "# 测试文章标题" in content or "测试文章标题" in content
            assert "这是正文内容" in content
    
    @pytest.mark.asyncio
    async def test_export_with_metadata(self, exporter, sample_content, tmp_path):
        """测试导出时包含元数据"""
        output_file = tmp_path / "test_with_metadata.md"
        
        # 添加元数据
        sample_content.metadata = {
            "author": "测试作者",
            "date": "2026-05-28"
        }
        
        result = await exporter.export(sample_content, str(output_file))
        
        # 验证元数据是否写入
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            # 检查是否包含元数据（具体格式取决于实现）
            assert "测试作者" in content or "author" in content.lower()
    
    def test_get_output_path(self, exporter):
        """测试获取输出路径"""
        from datetime import datetime
        
        content = Content(
            title="测试文章",
            content="内容",
            published_date=datetime(2026, 5, 28, 12, 0, 0)
        )
        
        # 调用获取输出路径的方法
        if hasattr(exporter, '_get_output_path'):
            path = exporter._get_output_path(content)
            assert path is not None
            assert isinstance(path, (str, Path))


class TestHTMLExporter:
    """测试 HTML 导出器"""
    
    @pytest.fixture
    def exporter(self):
        """创建 HTML 导出器实例"""
        try:
            from content_aggregator.exporters.html.exporter import HTMLExporter
            
            config = {"output_dir": "output", "template": "default"}
            return HTMLExporter(config)
        except ImportError:
            pytest.skip("HTML 导出器未实现")
    
    @pytest.fixture
    def sample_content(self):
        """创建测试内容"""
        return Content(
            title="测试文章",
            content="<h1>标题</h1><p>正文</p>",
            url="https://example.com/test"
        )
    
    @pytest.mark.asyncio
    async def test_export_html(self, exporter, sample_content, tmp_path):
        """测试导出 HTML 文件"""
        if exporter is None:
            pytest.skip("HTML 导出器未实现")
        
        output_file = tmp_path / "test_output.html"
        
        result = await exporter.export(sample_content, str(output_file))
        
        assert output_file.exists()
        
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "<html" in content.lower() or "测试文章" in content


class TestTXTExporter:
    """测试纯文本导出器"""
    
    @pytest.fixture
    def exporter(self):
        """创建 TXT 导出器实例"""
        try:
            from content_aggregator.exporters.txt import TXTExporter
            
            config = {"output_dir": "output"}
            return TXTExporter(config)
        except ImportError:
            pytest.skip("TXT 导出器未实现")
    
    @pytest.fixture
    def sample_content(self):
        """创建测试内容"""
        return Content(
            title="测试文章",
            content="这是纯文本内容。\n\n第二段落。",
            url="https://example.com/test"
        )
    
    @pytest.mark.asyncio
    async def test_export_txt(self, exporter, sample_content, tmp_path):
        """测试导出 TXT 文件"""
        if exporter is None:
            pytest.skip("TXT 导出器未实现")
        
        output_file = tmp_path / "test_output.txt"
        
        result = await exporter.export(sample_content, str(output_file))
        
        assert output_file.exists()
        
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "测试文章" in content
            assert "这是纯文本内容" in content


class TestPDFExporter:
    """测试 PDF 导出器"""
    
    @pytest.fixture
    def exporter(self):
        """创建 PDF 导出器实例"""
        try:
            from content_aggregator.exporters.pdf_exporter import PDFExporter
            
            config = {"output_dir": "output", "font": "simhei.ttf"}
            return PDFExporter(config)
        except ImportError:
            pytest.skip("PDF 导出器未实现")
    
    @pytest.fixture
    def sample_content(self):
        """创建测试内容"""
        return Content(
            title="测试PDF文章",
            content="这是PDF内容。\n\n第二页内容。",
            url="https://example.com/test"
        )
    
    @pytest.mark.asyncio
    async def test_export_pdf(self, exporter, sample_content, tmp_path):
        """测试导出 PDF 文件"""
        if exporter is None:
            pytest.skip("PDF 导出器未实现")
        
        output_file = tmp_path / "test_output.pdf"
        
        result = await exporter.export(sample_content, str(output_file))
        
        assert output_file.exists()
        assert output_file.stat().st_size > 0  # 文件不应该为空


class TestJSONExporter:
    """测试 JSON 导出器"""
    
    @pytest.fixture
    def exporter(self):
        """创建 JSON 导出器实例"""
        try:
            from content_aggregator.exporters.json.exporter import JSONExporter
            
            config = {"output_dir": "output"}
            return JSONExporter(config)
        except ImportError:
            pytest.skip("JSON 导出器未实现")
    
    @pytest.fixture
    def sample_content(self):
        """创建测试内容"""
        return Content(
            title="测试JSON文章",
            content="JSON内容",
            url="https://example.com/test"
        )
    
    @pytest.mark.asyncio
    async def test_export_json(self, exporter, sample_content, tmp_path):
        """测试导出 JSON 文件"""
        if exporter is None:
            pytest.skip("JSON 导出器未实现")
        
        output_file = tmp_path / "test_output.json"
        
        result = await exporter.export(sample_content, str(output_file))
        
        assert output_file.exists()
        
        # 验证 JSON 格式
        import json
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "title" in data
            assert data["title"] == "测试JSON文章"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
