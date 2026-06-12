"""Test RSS collection with proxy"""
import sys, yaml, asyncio, os

sys.path.insert(0, 'src')

from content_aggregator.workflows.pipeline import ContentPipeline

# 加载配置
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

print('Config loaded')
print(f'LLM provider: {config["llm"]["provider"]}')
print(f'HTTP proxy: {config.get("http", {}).get("proxy", "none")}')

# 测试 RSS（阮一峰，需要代理）
async def test_rss():
    # 阮一峰网络日志
    url = "http://feeds.feedburner.com/ruanyifeng"
    print(f'\nTesting RSS (阮一峰): {url}')
    
    async with ContentPipeline(config) as pipeline:
        article = await pipeline.process_url(url, rewrite=False)
        if article:
            print(f'Success! Title: {article.title}')
            print(f'Content length: {len(article.content)} chars')
            if len(article.content) > 100:
                print(f'Preview: {article.content[:150]}...')
        else:
            print('No article collected')
            return

        # 测试导出
        print('\nTesting exports...')
        path_md = pipeline.exporter.export(article, 'markdown')
        print(f'Markdown: {path_md}')
        
        path_html = pipeline.exporter.export(article, 'html')
        print(f'HTML: {path_html}')
        
        path_json = pipeline.exporter.export(article, 'json')
        print(f'JSON: {path_json}')

asyncio.run(test_rss())