"""
Content Aggregator - 测试脚本

用法：
    python scripts/run.py --url "https://example.com/rss.xml" --format markdown
    python scripts/run.py --url "https://example.com/rss.xml" --format html
    python scripts/run.py --url "https://example.com/rss.xml" --format json
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from content_aggregator.workflows.pipeline import ContentPipeline


def load_config():
    """加载配置文件"""
    import yaml

    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    # 默认配置
    return {
        "llm": {
            "provider": "deepseek",
            "api_key": "",  # 需要用户填入
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "max_tokens": 2000,
            "temperature": 0.7,
            "max_concurrency": 3,
        },
        "export": {
            "output_dir": "./output/exports",
            "default_format": "markdown",
        },
    }


async def main():
    parser = argparse.ArgumentParser(description="Content Aggregator CLI")
    parser.add_argument("--url", type=str, required=True, help="RSS URL to process")
    parser.add_argument("--format", type=str, default="markdown",
                        choices=["markdown", "html", "json", "txt", "xiaohongshu"],
                        help="Export format")
    parser.add_argument("--no-rewrite", action="store_true", help="Skip AI rewrite")
    parser.add_argument("--config", type=str, help="Config file path")

    args = parser.parse_args()

    # 加载配置
    if args.config:
        import yaml
        with open(args.config, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    else:
        config = load_config()

    # 检查 API key
    if not config.get("llm", {}).get("api_key"):
        print("Error: LLM API key not configured")
        print("Please set api_key in config/config.yaml")
        sys.exit(1)

    # 处理
    async with ContentPipeline(config) as pipeline:
        print(f"Processing: {args.url}")

        article = await pipeline.process_url(
            args.url,
            rewrite=not args.no_rewrite
        )

        if not article:
            print("Failed to process URL")
            sys.exit(1)

        print(f"Article: {article.title}")
        print(f"Word count: {article.word_count}")

        # 导出
        path = pipeline.exporter.export(article, args.format)
        print(f"Exported to: {path}")


if __name__ == "__main__":
    asyncio.run(main())