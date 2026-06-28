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

from loguru import logger

from content_aggregator.models import Content
from content_aggregator.clients.llm_client import LLMClient


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
    # 语气风格：formal（正式）/casual（口语）/academic（学术）
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
    内部使用统一的 LLMClient，无需额外翻译服务。

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
- Do NOT add explanations or notes

Output only the translated text.
""",
        TranslationLanguage.JAPANESE: """あなたはプロの翻訳者です。以下の中国語の記事を日本語に翻訳してください。

要件：
- 原文の意味とトーンを保持
- Markdownフォーマット（見出し、リスト、コードブロック等）を保持
- 自然で流暢な日本語を使用
- 説明や注釈を追加しない

翻訳テキストのみを出力してください。
""",
        TranslationLanguage.KOREAN: """당신은 전문 번역가입니다. 다음 중국어 기사를 한국어로 번역하세요.

요구사항:
- 원문의 의미와 톤을 유지
- 마크다운 포맷팅（제목, 목록, 코드 블록 등）유지
- 자연스럽고 유창한 한국어 사용
- 설명이나 주석 추가하지 마세요

번역된 텍스트만 출력하세요.
""",
        # 其他语言的提示词可以在这里添加
    }

    def __init__(self, config: dict[str, Any]):
        """
        初始化翻译处理器

        参数：
            config: 配置字典
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        # 使用统一的 LLMClient
        llm_cfg = dict(self.llm_config)
        http_proxy = (self.config.get("http", {}) or {}).get("proxy", "") or ""
        if http_proxy:
            llm_cfg["http_proxy"] = http_proxy
        self.llm_client = LLMClient(llm_cfg)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.llm_client.close()

    async def translate(
        self,
        content: Content,
        translation_config: TranslationConfig | None = None,
    ) -> TranslationResult:
        """
        翻译单篇内容

        参数：
            content: 原始内容对象
            translation_config: 翻译配置（可选）

        返回：
            TranslationResult 对象
        """
        if translation_config is None:
            translation_config = TranslationConfig()

        start_time = time.time()
        logger.info(f"[TranslatorProcessor.translate] START: {content.title[:60]}")

        try:
            # 构造提示词
            prompt = self._build_prompt(content, translation_config)

            logger.info(f"[TranslatorProcessor.translate] Prompt built, calling LLM...")

            # 调用 LLM（使用统一的 LLMClient）
            llm_response = await self.llm_client.call(prompt)

            logger.info(f"[TranslatorProcessor.translate] LLM response received, parsing...")

            response_text = llm_response["content"]
            usage = llm_response.get("usage", {})

            result = self._parse_response(response_text, content, translation_config, usage)
            result.duration = time.time() - start_time

            logger.info(f"[TranslatorProcessor.translate] SUCCESS: {content.title[:60]} -> {len(result.translated_content)} chars")

            return result

        except Exception as e:
            logger.error(f"[TranslatorProcessor.translate] FAILED: {e}")
            return TranslationResult(
                success=False,
                original_content=content,
                error=str(e),
                duration=time.time() - start_time,
            )

    def _build_prompt(self, content: Content, config: TranslationConfig) -> str:
        """
        构造翻译提示词

        优先级：
        1. config.custom_prompt（最高）
        2. TRANSLATION_PROMPTS[target_language]（语言特定）
        3. 默认通用提示词
        """
        # 1. 使用自定义提示词（如果提供）
        if config.custom_prompt:
            system_prompt = config.custom_prompt
        else:
            # 2. 使用语言特定的提示词
            system_prompt = self.TRANSLATION_PROMPTS.get(
                config.target_language,
                self.TRANSLATION_PROMPTS[TranslationLanguage.ENGLISH]  # 默认英语
            )

        # 添加语气和格式要求
        if config.tone == "formal":
            system_prompt += "\n\nIMPORTANT: Use formal, professional tone."
        elif config.tone == "academic":
            system_prompt += "\n\nIMPORTANT: Use academic, scholarly tone."

        if config.preserve_formatting:
            system_prompt += "\n\nIMPORTANT: Preserve all Markdown formatting (##, *, -, ```, etc.) exactly as they appear."

        user_prompt = f"""【原文标题】
{content.title}

【原文内容】
{content.content[:10000]}"""

        return f"{system_prompt}\n\n{user_prompt}"

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


# ============================
# 扩展指南
# ============================
# 如何为 TranslatorProcessor 添加新的目标语言支持：
#
# 1. 在 `TranslationLanguage` 枚举中添加新语言：
#    ```python
#    THAI = "th"  # 泰语
#    ```
#
# 2. 在 `TRANSLATION_PROMPTS` 字典中添加该语言的提示词：
#    ```python
#    TranslationLanguage.THAI: """... Thai translation prompt ..."""
#    ```
#
# 3. 更新配置文件示例（`config.yaml`）：
#    ```yaml
#    translate:
#      target_language: "th"  # 泰语
#      tone: "casual"
#      preserve_formatting: true
#    ```
#
# 4. 如果需要使用特定 LLM provider（如 ERNIE 对中文→泰语效果更好），
#   在 `config.yaml` 中指定 provider：
#    ```yaml
#    llm:
#      provider: "ernie"  # 使用文心一言进行翻译
#      model: "ernie-4.0-turbo-8k"
#      api_key: "your-client-id"
#      api_secret: "your-client-secret"
#    ```
