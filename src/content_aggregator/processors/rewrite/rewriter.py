"""
LLM 改写处理器

使用大语言模型对内容进行改写、摘要、风格迁移等处理。

支持策略：
- SUMMARIZE: 摘要提取
- STYLE_TRANSFER: 风格迁移
- PARAPHRASE: 伪原创
- REWRITE: 深度改写
- EXPAND: 内容扩展

使用示例：
    config = {
        "llm": {
            "provider": "deepseek",
            "api_key": "sk-xxx",
            "model": "deepseek-chat"
        }
    }

    async with RewriteProcessor(config) as processor:
        result = await processor.rewrite(content)
        if result.success:
            print(result.rewritten_content)
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from loguru import logger

from content_aggregator.models import Content


class RewriteStrategy(Enum):
    """
    改写策略枚举

    Attributes:
        SUMMARIZE: 摘要提取 - 从长文中提取核心要点
        STYLE_TRANSFER: 风格迁移 - 改变文章风格保持内容
        PARAPHRASE: 伪原创 - 同义改写保持原意
        REWRITE: 深度改写 - 重新组织结构和表达
        EXPAND: 内容扩展 - 添加背景案例数据
    """
    SUMMARIZE = "summarize"
    STYLE_TRANSFER = "style_transfer"
    PARAPHRASE = "paraphrase"
    REWRITE = "rewrite"
    EXPAND = "expand"


@dataclass
class RewriteConfig:
    """
    改写配置

    Attributes:
        strategy: 改写策略，默认 REWRITE
        style_id: 预设风格 ID（可选）
        style_config: 风格配置字典
        min_word_count: 最小字数
        max_word_count: 最大字数
        target_word_count: 目标字数
        translate_to: 翻译目标语言（如 "zh" 表示先翻译成中文再改写）
    """
    strategy: RewriteStrategy = RewriteStrategy.REWRITE
    style_id: str | None = None
    style_config: dict[str, Any] = field(default_factory=dict)
    min_word_count: int = 500
    max_word_count: int = 5000
    target_word_count: int = 3000
    translate_to: str | None = None


@dataclass
class RewriteResult:
    """
    改写结果

    Attributes:
        success: 是否成功
        original_content: 原始内容对象
        rewritten_content: 改写后的正文
        title: 改写后的标题
        summary: 摘要
        keywords: 关键词列表
        error: 错误信息
        duration: 处理耗时（秒）
        metadata: 元数据（token 使用量等）
    """
    success: bool
    original_content: Content | None = None
    rewritten_content: str = ""
    title: str = ""
    summary: str = ""
    keywords: list[str] = field(default_factory=list)
    error: str | None = None
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RewriteProcessor:
    """
    内容改写处理器

    使用大语言模型对内容进行改写处理。

    使用示例：
        config = {
            "llm": {
                "provider": "deepseek",
                "api_key": "sk-xxx",
                "model": "deepseek-chat",
                "base_url": "https://api.deepseek.com"
            }
        }

        async with RewriteProcessor(config) as processor:
            result = await processor.rewrite(content)
    """

    # 各策略对应的系统提示词
    SYSTEM_PROMPTS = {
        RewriteStrategy.SUMMARIZE: """你是一个专业的文章摘要助手。请根据提供的文章内容，提取核心要点，生成简洁准确的摘要。

要求：
1. 保留关键信息和核心观点
2. 语言简洁流畅
3. 长度控制在 200-500 字
4. 使用中文输出""",

        RewriteStrategy.STYLE_TRANSFER: """你是一个专业的文案风格转换助手。请将文章内容转换为指定的风格。

要求：
1. 保持原文的核心信息和观点
2. 严格按照指定的风格要求进行转换
3. 语言流畅自然
4. 使用中文输出""",

        RewriteStrategy.PARAPHRASE: """你是一个专业的伪原创助手。请在不改变原文核心意思的前提下，对文章进行改写，使其具有原创性。

要求：
1. 保持原文的核心信息和观点不变
2. 改变表达方式和句式结构
3. 替换同义词和近义词
4. 使用中文输出""",

        RewriteStrategy.REWRITE: """你是一个专业的文章改写助手。请对原文进行深度改写，重新组织结构和表达方式。

要求：
1. 保持原文的核心信息和主要观点
2. 重新组织文章结构和段落
3. 改变表达方式和句式
4. 使用中文输出""",

        RewriteStrategy.EXPAND: """你是一个专业的内容扩展助手。请在原文基础上添加更多背景、案例、数据等信息，生成更丰富的内容。

要求：
1. 保持原文的核心主题和观点
2. 添加相关的背景信息和行业数据
3. 引入更多实际案例
4. 使用中文输出""",
    }

    def __init__(self, config: dict[str, Any]):
        """
        初始化改写处理器

        参数：
            config: 配置字典，需包含 llm 配置
                - provider: LLM 提供商（deepseek/openai/qwen）
                - api_key: API 密钥
                - model: 模型名称
                - base_url: API 基础 URL（可选）
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RewriteProcessor":
        """异步上下文管理器入口"""
        timeout = self.llm_config.get("timeout", 120)
        self.client = httpx.AsyncClient(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器退出"""
        if self.client:
            await self.client.aclose()

    async def rewrite(
        self,
        content: Content,
        rewrite_config: RewriteConfig | None = None
    ) -> RewriteResult:
        """
        改写单篇内容

        参数：
            content: 待改写的内容对象
            rewrite_config: 改写配置（可选）

        返回：
            RewriteResult 对象
        """
        if rewrite_config is None:
            rewrite_config = RewriteConfig()

        start_time = time.time()

        try:
            prompt = self._build_prompt(content, rewrite_config)
            llm_response = await self._call_llm(prompt)
            response_text = llm_response["content"]
            usage = llm_response.get("usage", {})

            result = self._parse_response(response_text, content, rewrite_config, usage)
            result.duration = time.time() - start_time

            return result

        except Exception as e:
            logger.error(f"Rewrite error: {e}")
            return RewriteResult(
                success=False,
                original_content=content,
                error=str(e),
                duration=time.time() - start_time
            )

    async def rewrite_batch(
        self,
        contents: list[Content],
        rewrite_config: RewriteConfig | None = None
    ) -> list[RewriteResult]:
        """
        批量改写内容（带并发控制）

        参数：
            contents: 内容对象列表
            rewrite_config: 改写配置（可选）

        返回：
            RewriteResult 列表
        """
        if rewrite_config is None:
            rewrite_config = RewriteConfig()

        semaphore = asyncio.Semaphore(3)  # 并发限制为 3

        async def rewrite_with_limit(content: Content) -> RewriteResult:
            async with semaphore:
                return await self.rewrite(content, rewrite_config)

        tasks = [rewrite_with_limit(content) for content in contents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(RewriteResult(
                    success=False,
                    original_content=contents[i],
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    def _build_prompt(self, content: Content, config: RewriteConfig) -> str:
        """
        构建完整的提示词

        参数：
            content: 内容对象
            config: 改写配置

        返回：
            完整的提示词字符串
        """
        system_prompt = self.SYSTEM_PROMPTS.get(
            config.strategy,
            self.SYSTEM_PROMPTS[RewriteStrategy.REWRITE]
        )

        # 添加风格配置
        if config.style_config:
            style_rules = []
            tone = config.style_config.get("tone")
            if tone:
                style_rules.append(f"语气: {tone}")

            perspective = config.style_config.get("perspective")
            if perspective:
                perspective_map = {
                    "first_person": "第一人称",
                    "second_person": "第二人称",
                    "third_person": "第三人称"
                }
                style_rules.append(f"人称: {perspective_map.get(perspective, perspective)}")

            if style_rules:
                system_prompt += "\n\n风格要求:\n" + "\n".join(style_rules)

        # 字数要求
        system_prompt += (
            f"\n\n字数要求: {config.min_word_count}-{config.max_word_count} 字，"
            f"目标 {config.target_word_count} 字。"
        )

        # 原文
        user_prompt = f"""请处理以下文章:

【标题】
{content.title}

【正文】
{content.content[:10000]}
"""

        return f"{system_prompt}\n\n{user_prompt}"

    async def _call_llm(self, prompt: str) -> dict:
        """
        调用 LLM API

        参数：
            prompt: 提示词

        返回：
            包含 content 和 usage 的字典
        """
        provider = self.llm_config.get("provider", "deepseek")
        api_key = self.llm_config.get("api_key")
        model = self.llm_config.get("model", "deepseek-chat")
        base_url = self.llm_config.get("base_url", "https://api.deepseek.com")
        max_tokens = self.llm_config.get("max_tokens", 4096)

        if not api_key:
            raise ValueError("LLM API key is required")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        url = f"{base_url}/chat/completions"
        retry = self.llm_config.get("retry", 3)
        last_error = None

        for attempt in range(retry):
            try:
                response = await self.client.post(url, json=data, headers=headers)

                if response.status_code == 200:
                    result = response.json()
                    usage = result.get("usage", {})
                    return {
                        "content": result["choices"][0]["message"]["content"],
                        "usage": usage
                    }

                elif response.status_code == 429:
                    # 速率限制，指数退避
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                else:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)

            except Exception as e:
                last_error = e
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(1)

        raise Exception(f"LLM call failed after {retry} attempts: {last_error}")

    def _parse_response(
        self,
        response: str,
        original_content: Content,
        config: RewriteConfig,
        usage: dict[str, int] | None = None
    ) -> RewriteResult:
        """
        解析 LLM 响应

        参数：
            response: LLM 返回的原始文本
            original_content: 原始内容对象
            config: 改写配置
            usage: token 使用量

        返回：
            RewriteResult 对象
        """
        # 提取标题
        title = original_content.title
        title_match = re.search(r"【标题】[::]?\s*(.+?)(?:\n|$)", response)
        if title_match:
            title = title_match.group(1).strip()

        # 提取摘要
        summary = ""
        summary_match = re.search(
            r"【摘要】[::]?\s*(.+?)(?:\n【|\n\n|$)",
            response,
            re.DOTALL
        )
        if summary_match:
            summary = summary_match.group(1).strip()

        # 提取正文（移除标记部分）
        content_text = response
        for prefix in ["【标题】", "【摘要】", "标题:", "摘要:"]:
            if prefix in content_text:
                parts = content_text.split(prefix, 1)
                if len(parts) > 1:
                    content_text = parts[1]
                    for sep in ["\n【", "\n\n"]:
                        if sep in content_text:
                            content_text = content_text.split(sep, 1)[1]
                            break

        # 清理 LLM 生成的引导语
        intro_patterns = [
            r'^好的[，,]?请(?:先)?看以下为您[^。\n]+[。]?\s*',
            r'^以下是为您[^。\n]+[。]?\s*',
            r'^好的[，,]以下(?:内容|文章)[^。\n]*[。]?\s*',
            r'^好的[，,]?已为您[^。\n]+[。]?\s*',
            r'^好的[，,]?请(?:您)?欣赏[^。\n]*[。]?\s*',
        ]
        for pattern in intro_patterns:
            content_text = re.sub(pattern, "", content_text, count=1, flags=re.IGNORECASE)

        # 清理正文开头的摘要/标题标记行（非 SUMMARIZE 策略时）
        if config.strategy.value != 'SUMMARIZE':
            summary_prefixes = [
                r'\*\*摘要\*\*[：:]?\s*\n?',
                r'##\s*摘要[：:]?\s*\n?',
                r'【摘要】[：:]?\s*\n?',
                r'摘要[：:]\s*\n?',
                r'\*\*Abstract\*\*[：:]?\s*\n?',
            ]
            for sp in summary_prefixes:
                content_text = re.sub(sp, '', content_text, count=1)

        content_text = content_text.strip()

        # 提取关键词
        keywords = []
        kw_match = re.search(r"【关键词】[::]?\s*(.+?)(?:\n|$)", response)
        if kw_match:
            keywords = [k.strip() for k in kw_match.group(1).split(",")]

        # 元数据
        metadata = {
            "strategy": config.strategy.value,
            "original_length": len(original_content.content),
            "rewritten_length": len(content_text),
            "word_count": len(content_text),
        }

        if usage:
            metadata["tokens_used"] = usage.get("total_tokens", 0)
            metadata["prompt_tokens"] = usage.get("prompt_tokens", 0)
            metadata["completion_tokens"] = usage.get("completion_tokens", 0)

        return RewriteResult(
            success=True,
            original_content=original_content,
            rewritten_content=content_text,
            title=title,
            summary=summary or self._truncate(content_text, 200),
            keywords=keywords,
            metadata=metadata
        )

    def _truncate(self, text: str, length: int) -> str:
        """截断文本"""
        if len(text) <= length:
            return text
        return text[:length] + "..."