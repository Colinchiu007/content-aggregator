#!/usr/bin/env python3
"""
YouTube 采集诊断脚本 - 直接测试 pipeline.process_source("youtube")
用法：python diagnose_youtube_collect.py
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# 配置日志 - 输出到控制台和文件
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / "diagnose_youtube.log", mode='w', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 加载配置（模拟 server.py 中的 CONFIG）
try:
    import yaml
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        # 尝试其他可能的路径
        config_path = PROJECT_ROOT / "src" / "content_aggregator" / "config" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError("config.yaml not found in expected locations")
    
    with open(config_path, "r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f)
    logger.info(f"✅ 配置加载成功: {config_path}")
except Exception as e:
    logger.error(f"❌ 配置加载失败: {e}")
    CONFIG = {}

async def diagnose():
    """诊断 YouTube 采集"""
    logger.info("=" * 60)
    logger.info("开始诊断 YouTube 采集")
    logger.info("=" * 60)
    
    # 1. 检查配置
    logger.info("[1/5] 检查配置...")
    youtube_cfg = CONFIG.get("sources", {}).get("youtube", {})
    if not youtube_cfg:
        logger.warning("⚠️ 配置中没有 youtube 配置")
    else:
        logger.info(f"  API Key 存在: {'api_key' in youtube_cfg}")
        logger.info(f"  频道数量: {len(youtube_cfg.get('channels', []))}")
    
    # 2. 检查代理设置（检查两个位置：全局 http.proxy + youtube.proxy）
    logger.info("[2/5] 检查代理设置...")
    global_proxy = CONFIG.get("http", {}).get("proxy", "")
    youtube_proxy = youtube_cfg.get("proxy", "") if youtube_cfg else ""
    if global_proxy:
        logger.info(f"  全局代理已配置: {global_proxy}")
    elif youtube_proxy:
        logger.info(f"  YouTube 代理已配置: {youtube_proxy}")
    else:
        logger.info("  未配置代理")
    
    # 3. 创建 pipeline 并调用 process_source
    logger.info("[3/5] 创建 ContentPipeline...")
    try:
        from content_aggregator.workflows.pipeline import ContentPipeline
        async with ContentPipeline(CONFIG) as pipeline:
            logger.info("  ✅ ContentPipeline 创建成功")
            
            # 4. 调用 process_source("youtube")
            logger.info("[4/5] 调用 pipeline.process_source('youtube')...")
            result = await pipeline.process_source(
                source_type="youtube",
                rewrite=False,          # 先关闭改写，专注于采集
                translate=False,
                target_language=None,
                formats=["markdown"],
                limit_per_source=2,      # 只采集 2 个视频，方便测试
                progress_callback=None
            )
            
            # 5. 分析结果
            logger.info("[5/5] 分析采集结果...")
            summary = result.get("summary", {})
            articles = result.get("articles", [])
            
            logger.info(f"  成功任务数: {summary.get('success', 0)}")
            logger.info(f"  总文章数: {summary.get('total_articles', 0)}")
            logger.info(f"  文章数量: {len(articles)}")
            
            if summary.get('success', 0) == 0:
                logger.warning("⚠️ 采集成功数为 0，可能的问题：")
                logger.warning("  1. YouTube API Key 无效或配额用尽")
                logger.warning("  2. 代理配置错误，无法访问 YouTube API")
                logger.warning("  3. 频道 ID 无效或频道无视频")
                logger.warning("  4. youtube_transcript_api 无法访问（字幕获取）")
                logger.warning("  5. 代码异常被捕获，但未正确记录日志")
            else:
                logger.info("✅ 采集成功！")
                for i, article in enumerate(articles[:3], 1):  # 只显示前 3 篇
                    logger.info(f"  文章 {i}: {article.title[:50]}...")
    
    except Exception as e:
        logger.error(f"❌ 诊断过程中发生异常: {e}", exc_info=True)
    
    logger.info("=" * 60)
    logger.info("诊断完成，详细日志请查看: diagnose_youtube.log")
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(diagnose())
