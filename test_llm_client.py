"""
测试 LLMClient 和修改后的 rewrite/seo/translator 代码

验证：
1. LLMClient 可以正常调用 OpenAI 兼容接口
2. rewrite.py 使用 LLMClient 替代原有 _call_llm()
3. seo.py 使用 LLMClient 替代原有 _call_llm()
4. translator.py 使用 LLMClient 替代原有 _call_llm()
"""
import asyncio
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from content_aggregator.clients.llm_client import LLMClient
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
from content_aggregator.processors.seo import SEOProcessor, SEOConfig
from content_aggregator.processors.translator import TranslatorProcessor, TranslationConfig, TranslationLanguage
from content_aggregator.models import Content


# 测试配置（使用 DeepSeek 作为示例）
TEST_CONFIG = {
    "llm": {
        "provider": "deepseek",
        "api_key": "sk-ebc59537890a49b3a86aabef1ba1b8c7",  # 使用你的 API key
        "model": "deepseek-v3",
        "base_url": "https://api.deepseek.com",
        "max_tokens": 1024,
        "temperature": 0.7,
        "timeout": 120,
    }
}


async def test_llm_client():
    """测试 LLMClient 基本功能"""
    print("\n=== 测试 LLMClient ===")
    
    config = TEST_CONFIG["llm"]
    client = LLMClient(config)
    
    try:
        result = await client.call("用一句话介绍 Python")
        print(f"✅ LLMClient 调用成功")
        print(f"Content: {result['content'][:100]}...")
        print(f"Usage: {result['usage']}")
    except Exception as e:
        print(f"❌ LLMClient 调用失败: {e}")
    finally:
        await client.close()


async def test_rewrite():
    """测试 RewriteProcessor（使用 LLMClient）"""
    print("\n=== 测试 RewriteProcessor ===")
    
    # 创建测试内容
    test_content = Content(
        title="测试文章",
        content="Python 是一种广泛使用的高级编程语言，以简洁易读的语法著称。",
        url="https://example.com/test",
        source="test",
    )
    
    config = TEST_CONFIG
    async with RewriteProcessor(config) as processor:
        try:
            result = await processor.rewrite(
                test_content,
                RewriteConfig(strategy=RewriteStrategy.SUMMARIZE)
            )
            
            if result.success:
                print(f"✅ RewriteProcessor 调用成功")
                print(f"改写后标题: {result.title}")
                print(f"改写后内容: {result.rewritten_content[:100]}...")
            else:
                print(f"❌ RewriteProcessor 失败: {result.error}")
        except Exception as e:
            print(f"❌ RewriteProcessor 异常: {e}")


async def test_seo():
    """测试 SEOProcessor（使用 LLMClient）"""
    print("\n=== 测试 SEOProcessor ===")
    
    test_content = Content(
        title="Python 编程入门",
        content="Python 是一种广泛使用的高级编程语言...",
        url="https://example.com/python-intro",
        source="test",
    )
    
    config = TEST_CONFIG
    async with SEOProcessor(config) as seo:
        try:
            result = await seo.optimize(test_content, SEOConfig())
            
            if result.success:
                print(f"✅ SEOProcessor 调用成功")
                print(f"关键词: {result.keywords}")
                print(f"Meta 描述: {result.meta_description[:100]}...")
            else:
                print(f"❌ SEOProcessor 失败: {result.error}")
        except Exception as e:
            print(f"❌ SEOProcessor 异常: {e}")


async def test_translator():
    """测试 TranslatorProcessor（使用 LLMClient）"""
    print("\n=== 测试 TranslatorProcessor ===")
    
    test_content = Content(
        title="Python 简介",
        content="Python 是一种广泛使用的高级编程语言，以简洁易读的语法著称。",
        url="https://example.com/python-intro-zh",
        source="test",
    )
    
    config = TEST_CONFIG
    async with TranslatorProcessor(config) as translator:
        try:
            result = await translator.translate(
                test_content,
                TranslationConfig(target_language=TranslationLanguage.ENGLISH)
            )
            
            if result.success:
                print(f"✅ TranslatorProcessor 调用成功")
                print(f"翻译后标题: {result.title}")
                print(f"翻译后内容: {result.translated_content[:100]}...")
            else:
                print(f"❌ TranslatorProcessor 失败: {result.error}")
        except Exception as e:
            print(f"❌ TranslatorProcessor 异常: {e}")


async def main():
    """运行所有测试"""
    print("开始测试 LLMClient 和修改后的处理器...")
    
    # 逐个测试（避免同时发起太多请求）
    await test_llm_client()
    await asyncio.sleep(1)  # 避免速率限制
    
    await test_rewrite()
    await asyncio.sleep(1)
    
    await test_seo()
    await asyncio.sleep(1)
    
    await test_translator()
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
