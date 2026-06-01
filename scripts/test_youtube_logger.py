"""Test YouTube collector logger issue"""
import asyncio
import traceback
from content_aggregator.config import load_config
from content_aggregator.workflows.pipeline import ContentPipeline

async def test():
    cfg = load_config()
    async with ContentPipeline(cfg) as p:
        print('Pipeline created')
        entries = p._parse_single_config('youtube')
        print(f'YouTube entries: {len(entries)}')
        for e in entries:
            print(f'  - {e.get("name")}: {list(e.keys())}')

        if entries:
            from content_aggregator.sources import get_collector
            entry = entries[0]
            print(f'Testing collector for: {entry.get("name")}')
            try:
                collector = get_collector(
                    'youtube',
                    config=entry,
                    proxy=p.proxy,
                    timeout=30,
                )
                print(f'Collector created: {type(collector).__name__}')
                result = await collector.collect()
                print(f'Result: success={result.success}, error={result.error}')
            except Exception as ex:
                print(f'ERROR: {ex}')
                traceback.print_exc()

asyncio.run(test())
