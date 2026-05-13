"""
Content Aggregator - 命令行工具

用法：
    # 基础用法
    python scripts/run.py --url "https://example.com/rss.xml"

    # 指定导出格式（可多个）
    python scripts/run.py --url "https://example.com/rss.xml" --format markdown --format html

    # 批量处理（从文件读取 URL）
    python scripts/run.py --file urls.txt

    # 跳过 AI 改写
    python scripts/run.py --url "https://example.com/rss.xml" --no-rewrite

    # 限制采集数量
    python scripts/run.py --url "https://example.com/rss.xml" --limit 5

    # 指定改写策略
    python scripts/run.py --url "https://example.com/rss.xml" --strategy SUMMARIZE

    # 指定输出目录
    python scripts/run.py --url "https://example.com/rss.xml" --output ./my-output

    # 安静模式
    python scripts/run.py --url "https://example.com/rss.xml" --quiet
"""

import asyncio
import argparse
import sys
import time
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from content_aggregator.workflows.pipeline import ContentPipeline


def load_config(config_path: str | None = None) -> dict:
    """加载配置文件"""
    import yaml

    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).parent.parent / "config" / "config.yaml"

    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    # 默认配置
    return {
        "llm": {
            "provider": "deepseek",
            "api_key": "",  # 需要用户填入
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "max_tokens": 4096,
            "timeout": 120,
            "retry": 3,
        },
        "export": {
            "output_dir": "./output/exports",
        },
    }


async def process_single(
    pipeline: ContentPipeline,
    url: str,
    formats: list[str],
    rewrite: bool,
    seo: bool,
    verbose: bool
) -> dict:
    """
    处理单个 URL

    参数：
        pipeline: ContentPipeline 实例
        url: RSS URL
        formats: 导出格式列表
        rewrite: 是否改写
        seo: 是否 SEO 优化
        verbose: 是否显示详细信息

    返回：
        结果字典
    """
    start = time.time()

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"Processing: {url}")
        print(f"{'=' * 60}")

    # 采集 + 改写 + SEO
    article = await pipeline.process_url(url, rewrite=rewrite, seo=seo)

    if not article:
        return {
            "url": url,
            "success": False,
            "error": "Failed to process URL",
        }

    if verbose:
        print(f"\n[OK] Title: {article.title}")
        print(f"      Word count: {article.word_count}")
        if rewrite:
            print(f"      Rewrite: {article.rewrite_status}")

    # 导出
    paths = []
    for fmt in formats:
        try:
            path = pipeline.exporter.export(article, fmt)
            paths.append(path)
            if verbose:
                print(f"      Exported ({fmt}): {path}")
        except Exception as e:
            logger.error(f"Export failed ({fmt}): {e}")
            if verbose:
                print(f"      [ERROR] Export failed ({fmt}): {e}")

    elapsed = time.time() - start

    return {
        "url": url,
        "success": True,
        "article": article,
        "paths": paths,
        "elapsed": elapsed,
    }


async def process_batch(
    pipeline: ContentPipeline,
    urls: list[str],
    formats: list[str],
    rewrite: bool,
    limit: int | None,
    verbose: bool
) -> list[dict]:
    """
    批量处理 URL

    参数：
        pipeline: ContentPipeline 实例
        urls: URL 列表
        formats: 导出格式列表
        rewrite: 是否改写
        limit: 限制数量
        verbose: 是否显示详细信息

    返回：
        结果列表
    """
    if limit:
        urls = urls[:limit]

    print(f"\nTotal URLs to process: {len(urls)}")
    print(f"Formats: {', '.join(formats)}")
    print(f"Rewrite: {rewrite}")
    print(f"{'=' * 60}")

    results = []
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Processing...")
        result = await process_single(pipeline, url, formats, rewrite, seo, verbose)
        results.append(result)

    return results


def print_summary(results: list[dict], elapsed_total: float):
    """打印汇总信息"""
    success = sum(1 for r in results if r["success"])
    failed = len(results) - success
    total_files = sum(len(r.get("paths", [])) for r in results if r["success"])

    print(f"\n{'=' * 60}")
    print(f"Summary")
    print(f"{'=' * 60}")
    print(f"  Total: {len(results)}")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Files exported: {total_files}")
    print(f"  Total time: {elapsed_total:.2f}s")
    print(f"{'=' * 60}")


async def main():
    parser = argparse.ArgumentParser(
        description="Content Aggregator CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础用法
  python scripts/run.py --url "https://example.com/rss.xml"

  # 批量处理
  python scripts/run.py --file urls.txt --format markdown --format html

  # 跳过改写
  python scripts/run.py --url "https://example.com/rss.xml" --no-rewrite

  # 限制数量
  python scripts/run.py --file urls.txt --limit 10
"""
    )

    # 输入源
    input_group = parser.add_mutually_exclusive_group(required=False)
    input_group.add_argument("--url", type=str, help="单个 RSS URL")
    input_group.add_argument("--file", type=str, help="包含多个 URL 的文件（每行一个）")
    input_group.add_argument("--all-sources", action="store_true", help="采集 config.yaml 中所有已启用的数据源")

    # 导出格式
    parser.add_argument(
        "--format",
        type=str,
        action="append",
        choices=["markdown", "md", "html", "wechat", "json", "json-compact", "txt", "xiaohongshu", "xhs"],
        default=None,
        help="导出格式（可多次指定）"
    )

    # 处理选项
    parser.add_argument("--no-rewrite", action="store_true", help="跳过 AI 改写")
    parser.add_argument("--seo", action="store_true", help="对采集内容进行 SEO 优化（关键词/描述/标签）")
    parser.add_argument("--translate", type=str, nargs="?", const="EN",
                        help="翻译为指定语言（如 EN / JA / KO），不传参数默认英文")
    parser.add_argument("--limit", type=int, help="限制处理数量")
    parser.add_argument("--limit-per-source", type=int, default=20, help="每个数据源最大采集数（默认 20）")
    parser.add_argument("--strategy", type=str,
                        choices=["SUMMARIZE", "STYLE_TRANSFER", "PARAPHRASE", "REWRITE", "EXPAND"],
                        help="改写策略（需要 API 支持）")

    # 输出选项
    parser.add_argument("--output", type=str, help="输出目录")
    parser.add_argument("--config", type=str, help="配置文件路径")

    # 日志选项
    parser.add_argument("--quiet", action="store_true", help="安静模式（不显示详细信息）")
    parser.add_argument("--verbose", action="store_true", help="详细模式（显示更多信息）")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 覆盖配置
    if args.output:
        config.setdefault("export", {})["output_dir"] = args.output

    if args.strategy:
        config.setdefault("rewrite", {})["default_strategy"] = args.strategy

    # 检查 API key
    if not args.no_rewrite and not config.get("llm", {}).get("api_key"):
        print("Error: LLM API key not configured")
        print("Please set api_key in config/config.yaml or use --no-rewrite")
        sys.exit(1)

    # 确定导出格式
    formats = args.format if args.format else ["markdown"]
    # 去重
    formats = list(dict.fromkeys(formats))

    # 检查 API key
    if not args.no_rewrite and not config.get("llm", {}).get("api_key"):
        if not args.all_sources:
            print("Error: LLM API key not configured")
            print("Please set api_key in config/config.yaml or use --no-rewrite")
            sys.exit(1)
        else:
            print("[WARN] LLM API key not configured, skipping rewrite")

    # ---- 全源采集模式 ----
    if args.all_sources:
        print("\n📦 全源采集模式")
        print(f"  格式: {', '.join(formats)}")
        print(f"  改写: {not args.no_rewrite}")
        print(f"  SEO: {args.seo}")
        print(f"  翻译: {args.translate or '关闭'}")
        print(f"{'=' * 60}")

        start_total = time.time()
        async with ContentPipeline(config) as pipeline:
            result = await pipeline.process_all_sources(
                rewrite=not args.no_rewrite,
                translate=bool(args.translate),
                target_language=args.translate,
                seo=args.seo,
                formats=formats,
                limit_per_source=args.limit_per_source,
            )
        sys.exit(0)

    # ---- 单 URL / 文件模式 ----

    # 采集 URL 列表
    urls = []
    if args.url:
        urls = [args.url]
    elif args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        with open(file_path, encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        print("Error: No URLs to process")
        print("提示: 使用 --all-sources 采集所有已配置的数据源")
        sys.exit(1)

    # 配置日志
    if args.quiet:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")
    elif args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # 处理
    start_total = time.time()

    async with ContentPipeline(config) as pipeline:
        results = await process_batch(
            pipeline=pipeline,
            urls=urls,
            formats=formats,
            rewrite=not args.no_rewrite,
            seo=args.seo,
            verbose=not args.quiet
        )

    elapsed_total = time.time() - start_total

    # 汇总
    if not args.quiet:
        print_summary(results, elapsed_total)

    # 退出码
    failed = sum(1 for r in results if not r["success"])
    sys.exit(failed)


if __name__ == "__main__":
    asyncio.run(main())
