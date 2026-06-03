#!/usr/bin/env python
"""端到端测试：全源采集（仅测试三个新热点源）"""
import sys, asyncio, yaml
sys.path.insert(0, 'src')

from content_aggregator.workflows.pipeline import ContentPipeline

async def main():
    with open('config/config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 只启用三个新热点源，其他源禁用
    for k in config.get('sources', {}):
        if k not in ('douyin_hot', 'wangyi', 'weibo_hot'):
            # 对于列表类型的源（如 rss），将每个条目设为 disabled
            val = config['sources'][k]
            if isinstance(val, list):
                config['sources'][k] = [{**item, 'enabled': False} for item in val]
            elif isinstance(val, dict):
                config['sources'][k] = {'enabled': False}
    
    # 限制每个源采集数量，加快测试
    config['sources']['douyin_hot']['limit'] = 3
    config['sources']['wangyi']['limit'] = 3
    config['sources']['weibo_hot']['limit'] = 5
    config['llm'] = {'provider': 'none'}  # 跳过改写
    config['export'] = {'output_dir': './output/test'}
    
    print(f"配置源: {[k for k,v in config['sources'].items() if isinstance(v, dict) and v.get('enabled')]}")
    
    pipeline = ContentPipeline(config)
    
    result = await pipeline.process_all_sources(
        rewrite=False,
        formats=['markdown'],
        limit_per_source=None,
        progress_callback=None,  # 跳过进度回调，避免编码问题
    )
    
    print(f"\n{'='*60}")
    print(f"汇总")
    print(f"{'='*60}")
    summary = result['summary']
    print(f"  源总数: {summary['total_sources']}")
    print(f"  成功: {summary['success']}")
    print(f"  文章总数: {summary['total_articles']}")
    print(f"  耗时: {summary['elapsed']:.1f}s")
    
    for sr in result['source_results']:
        status = '[OK]' if sr['success'] else '[FAIL]'
        err = f" ({sr['error'][:50]})" if sr.get('error') else ""
        print(f"  {status} {sr['source_name']}: {sr['collected']} 篇{err}")
    
    for article in result['articles'][:5]:
        print(f"\n  [ARTICLE] {article.title[:70]}")
        print(f"     Source: {article.source} | Words: {article.word_count}")

asyncio.run(main())
