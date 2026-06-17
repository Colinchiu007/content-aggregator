"""AI 改写服务 — 通过 LLM API 实现多风格改写"""

import logging
from uuid import UUID

import httpx

from app.config import get_settings
from app.core.exceptions import ServiceError
from app.database import AsyncSessionLocal
from app.models.article import Article

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 改写风格 Prompt 模板
# ──────────────────────────────────────────────

STYLE_PROMPTS: dict[str, str] = {
    "轻松易懂": (
        "你是一位擅长社交媒体写作的内容专家。请将以下文章改写成「轻松易懂」风格。\n"
        "要求：\n"
        "- 语言口语化，使用短句和日常用语\n"
        "- 可以适当使用 emoji 增加亲和力\n"
        "- 保留原文的核心观点和关键数据\n"
        "- 让读者感觉像朋友在聊天"
    ),
    "正式严谨": (
        "你是一位专业的技术文档撰写人。请将以下文章改写成「正式严谨」风格。\n"
        "要求：\n"
        "- 使用规范的专业术语和正式表达\n"
        "- 逻辑严密，段落结构清晰\n"
        "- 保留原文的核心观点和关键数据\n"
        "- 适合官网、报告等正式场合发布"
    ),
    "吸引眼球": (
        "你是一位顶尖的营销文案写手。请将以下文章改写成「吸引眼球」风格。\n"
        "要求：\n"
        "- 标题要抓人眼球，可以使用数字、疑问、夸张等手法\n"
        "- 开头要有冲击力，快速抓住读者注意力\n"
        "- 使用短段落和列表提升可读性\n"
        "- 保留原文的核心观点和关键数据\n"
        "- 适合微信公众号、头条等流量分发平台"
    ),
    "深度分析": (
        "你是一位资深行业分析师。请将以下文章改写成「深度分析」风格。\n"
        "要求：\n"
        "- 深入剖析问题本质，提供多角度分析\n"
        "- 使用逻辑严密的论证结构\n"
        "- 保留原文的核心观点和关键数据，并适当展开\n"
        "- 适合知乎专栏、公众号长文等深度阅读场景"
    ),
}

# 长度策略
LENGTH_INSTRUCTIONS: dict[str, str] = {
    "keep": "请保持改写后的内容与原文长度相近（±10%）。",
    "compress": "请将内容压缩至原文的 70% 左右，提炼核心观点。",
    "expand": "请将内容扩展至原文的 130% 左右，丰富细节和案例。",
}


async def rewrite_article(
    article_id: UUID,
    style: str,
    length: str = "keep",
    seo_optimize: bool = False,
) -> dict:
    """对指定文章进行 AI 改写

    Args:
        article_id: 文章 ID
        style: 改写风格（轻松易懂 / 正式严谨 / 吸引眼球 / 深度分析）
        length: 长度策略（keep / compress / expand）
        seo_optimize: 是否启用 SEO 优化

    Returns:
        dict 包含:
          - article_id: 文章 ID
          - result_content: 改写后的内容
          - word_count: 改写后词数
          - style: 使用的风格

    Raises:
        NotFoundError: 文章不存在
        ServiceError: LLM API 调用失败
    """
    settings = get_settings()

    # 1. 从数据库加载原文
    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article:
            from app.core.exceptions import NotFoundError
            raise NotFoundError(f"文章不存在: {article_id}")

        source_content = article.source_content or ""
        if not source_content.strip():
            raise ServiceError("文章内容为空，无法改写")

    # 2. 构建 Prompt
    style_prompt = STYLE_PROMPTS.get(style)
    if not style_prompt:
        allowed = list(STYLE_PROMPTS.keys())
        from app.core.exceptions import ValidationError
        raise ValidationError(f"不支持的改写风格: {style}，可选值: {', '.join(allowed)}")

    length_instruction = LENGTH_INSTRUCTIONS.get(length, LENGTH_INSTRUCTIONS["keep"])
    seo_instruction = (
        "请对改写后的标题和正文进行 SEO 优化，合理嵌入目标关键词。"
        if seo_optimize
        else ""
    )

    system_prompt = (
        f"{style_prompt}\n"
        f"{length_instruction}\n"
        f"{seo_instruction}\n"
        "只输出改写后的正文内容，不要包含任何前言或说明。"
    )

    # 3. 调用 LLM API
    result_content = await _call_llm(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        model=settings.OPENAI_MODEL,
        system_prompt=system_prompt,
        user_content=source_content,
    )

    word_count = _count_words(result_content)
    logger.info(
        f"改写完成: article={article_id}, style={style}, "
        f"original={article.word_count_original}, result={word_count}"
    )

    return {
        "article_id": article_id,
        "result_content": result_content,
        "word_count": word_count,
        "style": style,
    }


async def _call_llm(
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_content: str,
) -> str:
    """调用 OpenAI 兼容的 LLM API

    Raises:
        ServiceError: API 调用失败或没有可用的 API Key
    """
    if not api_key:
        raise ServiceError(
            "未配置 LLM API Key，请在 .env 中设置 OPENAI_API_KEY"
        )

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
        "max_tokens": 4096,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            return content.strip()

    except httpx.HTTPError as e:
        logger.error(f"LLM API 调用失败: {e}")
        raise ServiceError(f"AI 改写服务暂时不可用: {e}") from e
    except (KeyError, IndexError) as e:
        logger.error(f"LLM API 响应格式异常: {e}")
        raise ServiceError("AI 改写返回格式异常，请稍后重试") from e


def _count_words(text: str) -> int:
    """中英文混合词数统计"""
    import re
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return chinese_chars + english_words
