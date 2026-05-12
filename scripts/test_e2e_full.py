"""
端到端测试：RSS采集 -> 翻译 -> PDF导出

测试流程：
1. RSS 采集阮一峰网络日志最新文章
2. 翻译成英文
3. 导出为 PDF

用法：
    python scripts/test_e2e_full.py [--no-proxy] [--skip-rewrite]
"""

import asyncio
import sys
import time
import uuid
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.processors.translator import TranslatorProcessor, TranslationLanguage, TranslationConfig
from content_aggregator.exporters.pdf_exporter import PDFExporter
from content_aggregator.models import Content, Article

# 测试用的 RSS URL
TEST_RSS_URL = "http://feeds.feedburner.com/ruanyifeng"


def load_config() -> dict:
    """加载配置"""
    import yaml

    path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


async def main():
    print("\n" + "=" * 60)
    print("Content Aggregator 端到端测试")
    print("=" * 60)

    config = load_config()

    # 1. RSS 采集
    print("\n[1/4] RSS 采集...")
    print(f"      URL: {TEST_RSS_URL}")
    start = time.time()

    try:
        async with ContentPipeline(config) as pipeline:
            article = await pipeline.process_url(TEST_RSS_URL, rewrite=False)

            if not article:
                print("      [ERROR] 采集失败")
                return False

            print(f"      [OK] 标题: {article.title}")
            print(f"      [OK] 字数: {article.word_count}")
            print(f"      [OK] 来源: {article.source}")

            # 2. 翻译
            print("\n[2/4] 翻译为英文...")
            start_translate = time.time()

            try:
                async with TranslatorProcessor(config) as translator:
                    # 构建 Content 对象供翻译器使用
                    content_obj = Content(
                        id=str(uuid.uuid4()),
                        source_id=article.source,
                        source_type="rss",
                        title=article.title,
                        content=article.content,
                        author=article.author,
                    )
                    translated = await translator.translate(
                        content_obj,
                        TranslationConfig(target_language=TranslationLanguage.ENGLISH)
                    )

                    if not translated.success:
                        print(f"      [ERROR] 翻译失败: {translated.error}")
                        return False

                    print(f"      [OK] 翻译完成")
                    print(f"      字数: {len(translated.translated_content)} 字符")
                    print(f"      耗时: {time.time() - start_translate:.1f}s")
                    print(f"\n      --- 翻译预览 (前 300 字) ---")
                    print(translated.translated_content[:300])
                    print("      --- 预览结束 ---\n")

            except Exception as e:
                print(f"      [ERROR] 翻译失败: {e}")
                import traceback; traceback.print_exc()
                return False

            # 3. PDF 导出
            print("[3/4] PDF 导出...")
            start_pdf = time.time()

            try:
                exporter = PDFExporter()
                if not exporter.available:
                    print("      [SKIP] reportlab 未安装，跳过 PDF 测试")
                    print("      提示: pip install reportlab")
                else:
                    output_path = Path(__file__).parent.parent / "output" / "exports" / f"test_translated_{int(time.time())}.pdf"
                    result = exporter.export_from_html(
                        html_content=translated.translated_content,
                        output_path=str(output_path),
                        title=article.title + " (English)",
                    )

                    if result.success:
                        print(f"      [OK] PDF 生成成功")
                        print(f"      路径: {result.file_path}")
                        print(f"      大小: {result.file_size / 1024:.1f} KB")
                        print(f"      耗时: {time.time() - start_pdf:.1f}s")
                    else:
                        print(f"      [ERROR] PDF 导出失败: {result.error}")

            except Exception as e:
                print(f"      [ERROR] PDF 导出异常: {e}")

            # 4. 其他格式导出测试
            print("\n[4/4] 其他格式导出测试...")

            try:
                # 构建翻译后的 Article
                translated_article = Article(
                    id=str(uuid.uuid4()),
                    title=f"{article.title} (EN)",
                    content=translated.translated_content,
                    source=article.source,
                    source_url=article.source_url,
                    author=article.author,
                    word_count=len(translated.translated_content),
                )

                # Markdown
                from content_aggregator.exporters import Exporter
                exporter2 = Exporter(str(Path(__file__).parent.parent / "output" / "exports"))

                md_path = exporter2.export(translated_article, "markdown")
                print(f"      [OK] Markdown: {md_path}")

                # HTML
                html_path = exporter2.export(translated_article, "html")
                print(f"      [OK] HTML: {html_path}")

                # JSON
                json_path = exporter2.export(translated_article, "json")
                print(f"      [OK] JSON: {json_path}")

                # 小红书
                xhs_path = exporter2.export(translated_article, "xiaohongshu")
                print(f"      [OK] 小红书: {xhs_path}")

            except Exception as e:
                print(f"      [ERROR] 导出失败: {e}")
                import traceback
                traceback.print_exc()

    except Exception as e:
        print(f"\n[ERROR] 流程异常: {e}")
        import traceback
        traceback.print_exc()
        return False

    total_time = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"测试完成！总耗时: {total_time:.1f}s")
    print(f"{'=' * 60}\n")

    return True


if __name__ == "__main__":
    asyncio.run(main())
