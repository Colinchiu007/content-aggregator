"""快速测试翻译API"""
import asyncio
import sys
import uuid
import time
sys.path.insert(0, 'src')

from content_aggregator.processors.translator import TranslatorProcessor, TranslationConfig, TranslationLanguage
from content_aggregator.models import Content

async def test():
    config = {"llm": {"provider": "deepseek", "api_key": "sk-c779fcc0cf7c48beaa3a330d72906739", "model": "deepseek-v4-pro", "base_url": "https://api.deepseek.com"}}
    content = Content(id=str(uuid.uuid4()), source_id="test", source_type="test", title="测试", content="今天天气真好")
    
    async with TranslatorProcessor(config) as t:
        start = time.time()
        result = await t.translate(content, TranslationConfig(target_language=TranslationLanguage.ENGLISH))
        print(f"Success: {result.success}")
        print(f"Translated: '{result.translated_content}'")
        print(f"Error: {result.error}")
        print(f"Metadata: {result.metadata}")
        print(f"Duration: {time.time()-start:.1f}s")

asyncio.run(test())
