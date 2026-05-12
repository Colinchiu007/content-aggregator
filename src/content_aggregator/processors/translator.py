"""
多语言翻译处理器

支持中文文章翻译为英文、日文、韩文等，目标语言可配置。
基于 LLM API 实现，保持原文语义和风格。
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from loguru import logger

from content_aggregator.models import Content


class TranslationLanguage(Enum):
    """目标语言"""
    ENGLISH = "en"          # 英语
    JAPANESE = "ja"         # 日语
    KOREAN = "ko"           # 韩语
    FRENCH = "fr"           # 法语
    GERMAN = "de"           # 德语
    SPANISH = "es"          # 西班牙语
    PORTUGUESE = "pt"       # 葡萄牙语
    RUSSIAN = "ru"          # 俄语
    ARABIC = "ar"           # 阿拉伯语
    VIETNAMESE = "vi"       # 越南语

    @property
    def display_name(self) -> str:
        names = {
            self.ENGLISH: "英语",
            self.JAPANESE: "日语",
            self.KOREAN: "韩语",
            self.FRENCH: "法语",
            self.GERMAN: "德语",
            self.SPANISH: "西班牙语",
            self.PORTUGUESE: "葡萄牙语",
            self.RUSSIAN: "俄语",
            self.ARABIC: "阿拉伯语",
            self.VIETNAMESE: "越南语",
        }
        return names.get(self, self.value)


@dataclass
class TranslationConfig:
    """翻译配置"""
    target_language: TranslationLanguage = TranslationLanguage.ENGLISH
    # 自定义翻译提示词（覆盖默认）
    custom_prompt: str | None = None
    # 语气风格：formal（正式）/ casual（口语）/ academic（学术）
    tone: str = "casual"
    # 保留原文格式（如 Markdown 标记）
    preserve_formatting: bool = True
    # 最大 token 数
    max_tokens: int = 8192


@dataclass
class TranslationResult:
    """翻译结果"""
    success: bool
    original_content: Content | None = None
    translated_content: str = ""
    title: str = ""
    summary: str = ""
    error: str | None = None
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class TranslatorProcessor:
    """
    多语言翻译处理器

    将文章内容翻译为目标语言，保持语义和基本风格。
    内部使用 LLM API，无需额外翻译服务。

    使用示例：
        async with TranslatorProcessor(config) as processor:
            result = await processor.translate(content, config)

    翻译提示词优先级：
        1. TranslationConfig.custom_prompt（最高）
        2. 内置默认提示词
    """

    # 内置翻译提示词（每种语言一套）
    TRANSLATION_PROMPTS = {
        TranslationLanguage.ENGLISH: """You are a professional translator. Translate the following Chinese article into English.

Requirements:
- Preserve the original meaning and tone
- Keep Markdown formatting (headers, lists, code blocks, etc.)
- Use natural, fluent English
- For technical terms, keep Chinese original in parentheses if no standard English translation exists
- Title should be translated to be catchy in English
- Keep similar paragraph structure

Output format: Only the translated content, no explanations or notes.""",

        TranslationLanguage.JAPANESE: """あなたはプロフェッショナルな翻訳者です。以下の中国語の記事を日本語に翻訳してください。

要件：
- 元の意味と文体を保つ
- Markdown フォーマットを維持（見出し、リスト、コードブロックなど）
- 自然で流れる日本語を使用
- 技術用語は、適切な日本語訳がない場合は中国語原文を括弧で残す
- タイトルは日本語として自然で目を引くものに
- 元の段落構造を維持

出力形式：翻訳内容のみの説明や注釈なし。""",

        TranslationLanguage.KOREAN: """당신은 전문 번역가입니다. 다음 중국어 기사를 한국어로 번역해 주세요.

요구사항:
- 원문의 의미와 톤을 유지
- Markdown 서식 유지 (제목, 목록, 코드 블록 등)
- 자연스럽고 유창한 한국어 사용
- 기술 용어는 표준 한국어 번역이 없으면 중국어 원문을 괄호 안에 유지
- 제목은 한국어로 자연스럽고 눈에 띄는 것으로
- 원본 단락 구조 유지

출력 형식: 번역된 내용만, 설명이나 메모 없음.""",

        # 以下语言使用通用提示词
        "default": """You are a professional translator. Translate the following Chinese article into the target language.

Requirements:
- Preserve the original meaning and tone
- Keep Markdown formatting
- Use natural, fluent target language
- Keep similar paragraph structure
- Title should be natural in target language

Output: Only the translated content, no explanations."""
    }

    def __init__(self, config: dict[str, Any]):
        """
        初始化翻译处理器

        参数：
            config: 配置文件，包含 llm 配置（同 rewrite 模块）
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        timeout = self.llm_config.get("timeout", 120)
        self.client = httpx.AsyncClient(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def translate(
        self,
        content: Content,
        translation_config: TranslationConfig | None = None
    ) -> TranslationResult:
        """翻译单篇内容"""
        if translation_config is None:
            translation_config = TranslationConfig()

        start_time = time.time()

        try:
            prompt = self._build_prompt(content, translation_config)
            llm_response = await self._call_llm(prompt, translation_config)
            response_text = llm_response["content"]
            usage = llm_response.get("usage", {})

            result = self._parse_response(response_text, content, translation_config, usage)
            result.duration = time.time() - start_time

            return result

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return TranslationResult(
                success=False,
                original_content=content,
                error=str(e),
                duration=time.time() - start_time
            )

    async def translate_batch(
        self,
        contents: list[Content],
        translation_config: TranslationConfig | None = None
    ) -> list[TranslationResult]:
        """批量翻译（带并发控制）"""
        if translation_config is None:
            translation_config = TranslationConfig()

        semaphore = asyncio.Semaphore(
            self.llm_config.get("max_concurrency", 3)
        )

        async def translate_with_limit(content: Content) -> TranslationResult:
            async with semaphore:
                return await self.translate(content, translation_config)

        tasks = [translate_with_limit(content) for content in contents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TranslationResult(
                    success=False,
                    original_content=contents[i],
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    def _get_prompt(self, language: TranslationLanguage) -> str:
        """获取指定语言的翻译提示词"""
        if language in self.TRANSLATION_PROMPTS:
            return self.TRANSLATION_PROMPTS[language]
        return self.TRANSLATION_PROMPTS["default"]

    def _build_prompt(
        self,
        content: Content,
        config: TranslationConfig
    ) -> str:
        """构建完整的翻译提示词"""
        # 1. 优先使用自定义提示词
        if config.custom_prompt:
            return f"{config.custom_prompt}\n\n【原文标题】\n{content.title}\n\n【原文内容】\n{content.content[:10000]}"

        # 2. 构建默认提示词
        system_prompt = self._get_prompt(config.target_language)

        # 添加语气要求
        tone_map = {
            "formal": "Use formal language suitable for business/professional context.",
            "casual": "Use casual, conversational tone suitable for social media/blog.",
            "academic": "Use academic tone suitable for research papers or technical articles."
        }
        if config.tone in tone_map:
            system_prompt += f"\n\n{tone_map[config.tone]}"

        # 添加格式保留说明
        if config.preserve_formatting:
            system_prompt += "\n\nIMPORTANT: Preserve all Markdown formatting (##, *, -, ```, etc.) exactly as they appear."

        user_prompt = f"""【原文标题】
{content.title}

【原文内容】
{content.content[:10000]}"""

        return f"{system_prompt}\n\n{user_prompt}"

    async def _call_llm(
        self,
        prompt: str,
        config: TranslationConfig
    ) -> dict:
        """调用 LLM API"""
        provider = self.llm_config.get("provider", "deepseek")
        api_key = self.llm_config.get("api_key")
        model = self.llm_config.get("model", "deepseek-chat")
        base_url = self.llm_config.get("base_url", "https://api.deepseek.com")
        max_tokens = config.max_tokens

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
        config: TranslationConfig,
        usage: dict[str, int] | None = None
    ) -> TranslationResult:
        """解析 LLM 响应"""
        translated_text = response.strip()

        # 提取标题（可能带标记）
        title = translated_text.split("\n")[0] if "\n" in translated_text else translated_text[:200]
        # 清理标题中的 Markdown 标记
        title = title.lstrip("#").strip()

        # 提取正文（去掉标题后的内容）
        if "\n" in translated_text:
            body = "\n".join(translated_text.split("\n")[1:]).strip()
        else:
            body = translated_text

        metadata = {
            "target_language": config.target_language.value,
            "target_language_name": config.target_language.display_name,
            "tone": config.tone,
            "original_length": len(original_content.content),
            "translated_length": len(body),
            "preserve_formatting": config.preserve_formatting,
        }

        if usage:
            metadata["tokens_used"] = usage.get("total_tokens", 0)
            metadata["prompt_tokens"] = usage.get("prompt_tokens", 0)
            metadata["completion_tokens"] = usage.get("completion_tokens", 0)

        return TranslationResult(
            success=True,
            original_content=original_content,
            translated_content=body,
            title=title,
            summary=self._truncate(body, 200),
            metadata=metadata
        )

    def _truncate(self, text: str, length: int) -> str:
        """截断文本"""
        if len(text) <= length:
            return text
        return text[:length] + "..."