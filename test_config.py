#!/usr/bin/env python
"""测试配置解析"""
import sys, asyncio, yaml
sys.path.insert(0, 'src')
from content_aggregator.workflows.pipeline import ContentPipeline

async def test():
    with open('config/config.yaml', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    sources = config.get('sources', {})
    for k in ['douyin_hot', 'wangyi', 'weibo_hot']:
        v = sources.get(k, {})
        enabled = v.get('enabled', False)
        print(f'{k}: enabled={enabled}, config={v}')
    
    pipeline = ContentPipeline(config)
    for stype in ['douyin_hot', 'wangyi', 'weibo_hot']:
        entries = pipeline._parse_single_config(stype)
        print(f'{stype} -> {len(entries)} entries: {entries}')

asyncio.run(test())
