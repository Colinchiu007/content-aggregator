"""
SEO 优化处理器

基于 LLM 的智能 SEO 优化：关键词提取、Meta 描述生成、标签优化。

设计决策：
- 用 LLM 而非纯规则（TF-IDF），因为对中文语境理解更好
- 一次性调用生成所有 SEO 元素，减少 token 开销
- 返回结构化结果，不直接修改 Article，由调用方决定如何使用

使用示例：
    async with SEOProcessor(config) as seo:
        result = await seo.optimize(content)
        if result.success:
            print(result.keywords)      # ['AI', '机器学习', ...]
            print(result.meta_description)  # 160字以内的SEO描述
            print(result.optimized_tags)    # 优化后的标签
"""

import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from content_aggregator.models import Content
from content_aggregator.clients.llm_client import LLMClient


@dataclass
class SEOConfig:
    """
    SEO 优化配置

    Attributes:
        max_keywords: 最大关键词数量（默认 8）
        description_length: Meta 描述最大长度（默认 160 字符）
        max_tags: 最大标签数量（默认 5）
        language: 内容语言（zh-CN/en-US）
    """
    max_keywords: int = 8
    description_length: int = 160
    max_tags: int = 5
    language: str = "zh-CN"


@dataclass
class SEOResult:
    """
    SEO 优化结果

    Attributes:
        success: 是否成功
        keywords: 提取的关键词列表
        meta_description: 生成的 Meta Description
        meta_title: 优化的 Meta Title（可选）
        optimized_tags: 优化后的标签
        error: 错误信息
        duration: 处理耗时（秒）
    """
    success: bool
    keywords: list[str] = field(default_factory=list)
    meta_description: str = ""
    meta_title: str = ""
    optimized_tags: list[str] = field(default_factory=list)
    error: str | None = None
    duration: float = 0.0


class SEOProcessor:
    """
    SEO 优化处理器

    通过 LLM 一次性生成关键词、描述和标签，避免多次调用。

    Prompt 设计：要求 LLM 输出严格 JSON 格式，便于解析。
    """

    SYSTEM_PROMPT = """You are an SEO expert. Given an article title and content, generate SEO metadata in STRICT JSON format:

{
  "keywords": ["keyword1", "keyword2", ...],
  "meta_description": "A compelling description under {max_desc} characters for search engines",
  "meta_title": "An optimized title (optional, can be same as original if already good)",
  "tags": ["tag1", "tag2", ...]
}

Rules:
- keywords: Extract the most important keywords/phrases that users would search for. Max {max_kw} items.
- meta_description: Write a compelling, click-worthy description. Include primary keywords naturally. Under {max_desc} characters.
- meta_title: Keep or slightly improve the original title for better CTR. Under 60 characters.
- tags: Category-like tags for content organization. Max {max_tags} items.
- Language: Match the article's language ({lang}).
- Output ONLY valid JSON, no markdown, no explanation.
"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.llm_config = config.get("llm", {})
        # 使用统一的 LLMClient
        llm_cfg = dict(self.llm_config)
        http_proxy = (self.config.get("http", {}) or {}).get("proxy", "") or ""
        if http_proxy:
            llm_cfg["http_proxy"] = http_proxy
        self.llm_client = LLMClient(llm_cfg)

    async def __aenter__(self) -> "SEOProcessor":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.llm_client.close()

    async def optimize(
        self,
        content: Content,
        seo_config: SEOConfig | None = None,
    ) -> SEOResult:
        """
        对内容执行 SEO 优化

        参数：
            content: 原始内容对象
            seo_config: SEO 配置（可选）

        返回：
            SEOResult 结构化结果
        """
        if seo_config is None:
            seo_config = SEOConfig()

        start = time.time()

        try:
            # 构造 prompt
            # 避免 JSON 中的 {..} 被 .format() 误解析，逐个替换参数
            system = self.SYSTEM_PROMPT \
                .replace("{max_kw}", str(seo_config.max_keywords)) \
                .replace("{max_desc}", str(seo_config.description_length)) \
                .replace("{max_tags}", str(seo_config.max_tags)) \
                .replace("{lang}", seo_config.language)

            # 截取正文（避免 token 浪费，保留前 3000 字足够 SEO 分析）
            body = content.content[:3000] if content.content else ""
            if len(content.content or "") > 3000:
                body += "\n\n[... truncated for brevity ...]"

            user_prompt = f"Title: {content.title}\n\nContent:\n{body}"

            # 调用 LLM（使用统一的 LLMClient）
            # 构造完整 prompt（system + user）
            full_prompt = f"{system}\n\n{user_prompt}"
            result = await self.llm_client.call(full_prompt)

            if not result or not result.get("content"):
                return SEOResult(
                    success=False,
                    error="LLM returned empty response",
                    duration=time.time() - start,
                )

            # 解析 JSON
            parsed = self._parse_response(result["content"])

            return SEOResult(
                success=True,
                keywords=parsed.get("keywords", [])[:seo_config.max_keywords],
                meta_description=parsed.get("meta_description", ""),
                meta_title=parsed.get("meta_title", ""),
                optimized_tags=parsed.get("tags", [])[:seo_config.max_tags],
                duration=time.time() - start,
            )

        except Exception as e:
            logger.error(f"SEO optimization failed: {e}")
            return SEOResult(success=False, error=str(e), duration=time.time() - start)

    @staticmethod
    def _parse_response(text: str) -> dict:
        """
        解析 LLM 返回的 JSON

        容错处理：
        1. 提取 ```json ... ``` 代码块
        2. 直接 json.loads
        3. 提取第一个 { } 块
        """
        import json
        import re

        # 尝试提取代码块
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if m:
            text = m.group(1).strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 3. raw_decode
        try:
            decoder = json.JSONDecoder()
            result, _ = decoder.raw_decode(text)
            return result
        except json.JSONDecodeError:
            pass

        logger.warning(f"Failed to parse SEO response: {text[:200]}")
        return {}


# ============================
# 扩展指南
# ============================
"""
如何为 SEOProcessor 添加新的 LLM provider 支持：

1. 在 `content_aggregator/clients/llm_client.py` 中添加新的 `_call_xxx()` 方法
2. 在 `LLMClient.call()` 方法中添加新 provider 的路由逻辑
3. 更新配置文件支持新 provider

示例：添加 ERNIE 支持

1. 在 `llm_client.py` 中添加：
    ```python
    async def _call_ernie(self, prompt: str) -> dict:
        # ERNIE 特定逻辑（获取 access_token、构造请求等）
        ...
    ```

2. 在 `call()` 方法中添加路由：
    ```python
    elif self.provider == "ernie":
        return await self._call_ernie(prompt)
    ```

3. 更新 `config.yaml`：
    ```yaml
    llm:
      provider: "ernie"
      model: "ernie-4.0-turbo-8k"
      api_key: "your-client-id"
      api_secret: "your-client-secret"
    ```
"""
