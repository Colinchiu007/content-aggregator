"""
内容改写处理器
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import httpx
from loguru import logger

from content_aggregator.models import Content
from content_aggregator.clients.llm_client import LLMClient


class RewriteStrategy(Enum):
    """改写策略"""
    SUMMARIZE = "summarize"        # 摘要提取
    STYLE_TRANSFER = "style_transfer"  # 风格迁移
    PARAPHRASE = "paraphrase"      # 伪原创
    REWRITE = "rewrite"            # 深度改写
    EXPAND = "expand"              # 内容扩展
    SHORT_VIDEO = "short_video"    # 短视频文案仿写

    @property
    def display_name(self) -> str:
        names = {
            self.SUMMARIZE: "摘要提取",
            self.STYLE_TRANSFER: "风格迁移",
            self.PARAPHRASE: "伪原创",
            self.REWRITE: "深度改写",
            self.EXPAND: "内容扩展",
            self.SHORT_VIDEO: "短视频文案",
        }
        return names.get(self, self.value)


@dataclass
class RewriteConfig:
    """改写配置"""
    strategy: RewriteStrategy = RewriteStrategy.REWRITE
    style_id: str | None = None
    style_config: dict[str, Any] = field(default_factory=dict)
    min_word_count: int = 300
    max_word_count: int = 3000
    target_word_count: int = 1500
    # 自定义提示词(最高优先级,覆盖策略默认提示词和配置文件提示词)
    custom_prompt: str | None = None
    # 翻译目标语言。设为 "zh" 时先翻译成中文再改写
    translate_to: str | None = None
    # 原文语言代码(如 "en", "ja", "ko"),用于动态拼接翻译提示词
    source_language: str | None = None
    # 原文语言中文名称(如 "英文", "日文"),显示用
    source_language_name: str | None = None
    # 目标行业(可选,按行业语境改写)
    industry: str | None = None


@dataclass
class RewriteResult:
    """改写结果"""
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

    使用示例:
        async with RewriteProcessor(config) as processor:
            result = await processor.rewrite(content, config)

    提示词优先级:
        1. RewriteConfig.custom_prompt(最高)
        2. config['rewrite']['prompts'][strategy](配置文件)
        3. SYSTEM_PROMPTS(内置默认值)
    """

    DEFAULT_PROMPTS = {
        RewriteStrategy.SUMMARIZE: """你是一个专业的文章摘要助手。请根据提供的文章内容,提取核心要点,生成简洁准确的摘要。
直接输出结果,不要任何寒暄或前缀。
要求:
1. 保留关键信息和核心观点
2. 语言简洁流畅
3. 长度控制在200-500字
4. 使用中文输出""",

        RewriteStrategy.STYLE_TRANSFER: """你是一个专业的文案风格转换助手。请将文章内容转换为指定的风格。
直接输出结果,不要任何寒暄或前缀。
要求:
1. 保持原文的核心信息和观点
2. 严格按照指定的风格要求进行转换
3. 语言流畅自然
4. 使用中文输出""",

        RewriteStrategy.PARAPHRASE: """你是一个专业的伪原创助手。请在不改变原文核心意思的前提下,对文章进行改写,使其具有原创性。
同时改写标题,在正文前用【标题】标记改写后的标题。
直接输出结果,不要任何寒暄或前缀。
要求:
1. 保持原文的核心信息和观点不变
2. 改变表达方式和句式结构
3. 替换同义词和近义词
4. 使用中文输出""",

        RewriteStrategy.REWRITE: """你是一个专业的文章改写助手。请对原文进行深度改写,重新组织结构和表达方式。
要求:
1. 保持原文的核心信息和主要观点
2. 重新组织文章结构和段落
3. 改变表达方式和句式
4. 排除文章末尾的版权声明、免责声明、平台声明等非正文内容
5. 使用中文输出
6. 同时改写标题,在正文前用【标题】标记改写后的标题
7. 直接输出改写结果,不要任何寒暄、解释或前缀(如"好的,这是为您改写后的文章"等)""",

        RewriteStrategy.EXPAND: """你是一个专业的内容扩展助手。请在原文基础上添加更多背景、案例、数据等信息,生成更丰富的内容。
要求:
1. 保持原文的核心主题和观点
2. 添加相关的背景信息和行业数据
3. 引入更多实际案例
4. 排除文章末尾的版权声明、免责声明、平台声明等非正文内容
5. 使用中文输出
6. 同时改写标题,在正文前用【标题】标记改写后的标题
7. 直接输出结果,不要任何寒暄、解释或前缀""",

        RewriteStrategy.SHORT_VIDEO: """根据下面要求改写:
你是一名专业的短视频文案仿写专家,具备以下核心能力:
- 精准识别爆款短视频文案的选题角度和内容结构
- 保持40%-50%内容相似度的改写技巧
- 自然融入用户提供的替换信息
- 完美复现短视频特有的口语化、情感化表达风格

📝 任务指令模板

【仿写核心要求】
1. 选题一致性
  - 完全保持原文案的核心主题方向
  - 继承相同的价值主张和情感基调
2. 结构还原度
  - 段落数量和组织顺序完全一致
  - 保持相同的叙事逻辑(如:问题→经历→反思)
  - 保留原有的内容结构元素
3. 内容相似度控制
  - 保持40%-50%的内容相似度
  - 关键信息点必须保留
  - 通过以下方式实现差异化:
  - 调整具体描述用语
  - 改变事例细节但保留核心情节
  - 使用同义词替换但保持语义一致
  - 调整句子结构但传达相同信息

🔧 具体操作步骤
请严格按以下流程执行:

第一步:结构分析
  - 识别原文案的段落划分(如:个人经历→问题出现→反思总结)
  - 标记关键结构节点(转折点、情感高潮、结论部分)
第二步:内容要素提取
  - 核心主题:[例如:个人经历分享]
  - 情感主线:[例如:愧疚→反思→建议]
  - 关键信息点:[列出5-8个必须保留的核心信息]
  - 结构特色:[如:时间顺序叙事、问题解决方案等]
第三步:相似度控制改写
  - 保留50%核心内容:关键情节、主要观点、重要数据
  - 改写50%内容:具体描述、次要细节、表达方式
  - 检查标准:读起来像同一主题但不是同一篇文章
第四步:风格优化
  - 保持口语化表达和情感化语言
  - 确保最终文案长度与原文案相近

📋 输出格式要求
请输出仿写后的完整文案,包含:
  - 保持语句通顺,没有错别字
  - 严格保持原段落结构
  - 自然换行
  - 结尾保留类似的祝福或总结语
  - 文案里禁止出现任何emoji表情

【限制】
严禁你在输出的结果开头出现相应我的任何回答,比如"好的,这是为您优化的短视频文案,严格遵循您的指令和要求:"这样类似的话,我需要你直接输出结果。""",
    }

    def __init__(self, config: dict[str, Any]):
        """
        初始化处理器

        参数:
            config: 配置字典,支持从 config['rewrite']['prompts'] 覆盖提示词模板
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        self.rewrite_config = config.get("rewrite", {})
        # 使用统一的 LLMClient
        # 获取代理配置(跨模块传递 http_proxy)
        llm_cfg = dict(self.llm_config)
        http_proxy = (self.config.get("http", {}) or {}).get("proxy", "") or ""
        if http_proxy:
            llm_cfg["http_proxy"] = http_proxy
        self.llm_client = LLMClient(llm_cfg)
        # 从配置文件加载自定义提示词(覆盖默认值)
        self._custom_prompts: dict[str, str] = self.rewrite_config.get("prompts", {})

    async def __aenter__(self):
        # LLMClient 内部自己管理 HTTP 客户端
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.llm_client.close()

    async def rewrite(
        self,
        content: Content,
        rewrite_config: RewriteConfig | None = None,
        progress_callback: Callable | None = None
    ) -> RewriteResult:
        """改写单篇内容"""
        if rewrite_config is None:
            rewrite_config = RewriteConfig()

        start_time = time.time()
        logger.info(f"[RewriteProcessor.rewrite] START: {content.title[:60]}")

        try:
            # 报告进度:开始构建提示词
            if progress_callback:
                await progress_callback(0, 1, "正在构建提示词...", 5)

            prompt = self._build_prompt(content, rewrite_config)

            # 报告进度:开始调用 LLM(最耗时的步骤)
            if progress_callback:
                await progress_callback(0, 1, "正在调用 LLM 改写...", 10)

            logger.info(f"[RewriteProcessor.rewrite] Prompt built, calling LLM...")
            llm_response = await self.llm_client.call(prompt)

            # 报告进度:LLM 响应已收到,正在解析
            if progress_callback:
                await progress_callback(0, 1, "LLM 响应已收到,正在解析...", 60)

            logger.info(f"[RewriteProcessor.rewrite] LLM response received, parsing...")
            response_text = llm_response["content"]
            usage = llm_response.get("usage", {})

            result = self._parse_response(response_text, content, rewrite_config, usage)
            result.duration = time.time() - start_time
            logger.info(f"[RewriteProcessor.rewrite] SUCCESS: {content.title[:60]} -> {len(result.rewritten_content)} chars")

            # 报告进度:完成
            if progress_callback:
                await progress_callback(0, 1, "改写完成", 100)

            return result

        except Exception as e:
            logger.error(f"[RewriteProcessor.rewrite] ERROR: {content.title[:60]}: {e}", exc_info=True)
            return RewriteResult(
                success=False,
                original_content=content,
                error=str(e),
                duration=time.time() - start_time
            )

    async def rewrite_batch(
        self,
        contents: list[Content],
        rewrite_config: RewriteConfig | None = None,
        progress_callback: Callable | None = None
    ) -> list[RewriteResult]:
        """批量改写内容(带并发控制)"""
        if rewrite_config is None:
            rewrite_config = RewriteConfig()

        results = []
        semaphore = asyncio.Semaphore(3)
        completed = 0
        total = len(contents)

        async def rewrite_with_limit(content: Content, index: int) -> RewriteResult:
            nonlocal completed
            async with semaphore:
                # 报告进度(开始改写当前文章)
                if progress_callback:
                    progress = int(completed / total * 100) if total > 0 else 0
                    await progress_callback(completed, total, f"正在改写: {content.title[:30]}", progress)

                result = await self.rewrite(content, rewrite_config, progress_callback=None)  # 不传递回调,避免冲突

                completed += 1
                # 报告进度(完成当前文章)
                if progress_callback:
                    progress = int(completed / total * 100) if total > 0 else 100
                    await progress_callback(completed, total, f"完成改写: {content.title[:30]}", progress)

                return result

        tasks = [rewrite_with_limit(content, i) for i, content in enumerate(contents)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

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

    def _get_prompt(self, strategy: RewriteStrategy) -> str:
        """
        获取指定策略的提示词

        优先级:配置文件 > 默认值
        """
        strategy_key = strategy.value
        if strategy_key in self._custom_prompts and self._custom_prompts[strategy_key].strip():
            return self._custom_prompts[strategy_key]
        return self.DEFAULT_PROMPTS.get(strategy, self.DEFAULT_PROMPTS[RewriteStrategy.REWRITE])

    def _build_prompt(self, content: Content, config: RewriteConfig) -> str:
        """构建完整的提示词"""
        # 1. 优先使用 RewriteConfig 中的自定义提示词
        if config.custom_prompt:
            user_prompt = f"""请处理以下文章:

【标题】
{content.title}

【正文】
{content.content[:10000]}
"""
            return f"{config.custom_prompt}\n\n{user_prompt}"

        # 2. 从配置或默认值获取提示词
        system_prompt = self._get_prompt(config.strategy)

        # 翻译 + 改写（合并为一次 LLM 调用）
        if config.translate_to == "zh":
            source_lang = config.source_language_name or "非中文"
            translation_prefix = (
                f"【务必执行】原文为{source_lang}，必须先翻译为中文，再按下面要求改写。\n"
                "翻译要求：保留技术术语原文，其余全部译为中文。\n"
                "改写要求如下：\n"
                "========\n"
            )
            system_prompt = translation_prefix + system_prompt

        # 添加风格配置
        if config.style_config:
            style_rules = []
            tone = config.style_config.get("tone")
            if tone:
                style_rules.append(f"语气:{tone}")

            perspective = config.style_config.get("perspective")
            if perspective:
                perspective_map = {
                    "first_person": "第一人称",
                    "second_person": "第二人称",
                    "third_person": "第三人称"
                }
                style_rules.append(f"人称:{perspective_map.get(perspective, perspective)}")

            if style_rules:
                system_prompt += "\n\n风格要求:\n" + "\n".join(style_rules)

        # 行业定向(按行业语境改写)
        if config.industry:
            system_prompt += (
                f"\n\n目标行业:{config.industry}"
                f"\n请基于该行业的读者语境、专业术语和表达习惯进行改写。"
            )

        # 字数要求
        system_prompt += (
            f"\n\n字数要求:{config.min_word_count}-{config.max_word_count}字,"
            f"目标{config.target_word_count}字。"
        )

        # 原文
        user_prompt = f"""请处理以下文章:

【标题】
{content.title}

【正文】
{content.content[:10000]}
"""

        return f"{system_prompt}\n\n{user_prompt}"

    # _call_llm() 已删除,改用统一的 LLMClient
    # 如需自定义逻辑,在 LLMClient 中添加新的 _call_xxx() 方法

    def _parse_response(
        self,
        response: str,
        original_content: Content,
        config: RewriteConfig,
        usage: dict[str, int] | None = None
    ) -> RewriteResult:
        """解析 LLM 响应"""
        # 提取标题(修复解析逻辑)
        title = original_content.title
        # 方法1:标准格式 【标题】xxx
        if "【标题】" in response:
            title_match = re.search(r"【标题】\s*(.+?)(?:\n|$)", response)
            if title_match:
                title = title_match.group(1).strip()
        # 方法2:备用格式 标题: xxx
        elif "标题:" in response:
            title_match = re.search(r"标题:\s*(.+?)(?:\n|$)", response)
            if title_match:
                title = title_match.group(1).strip()

        # 清理标题中的 LLM 寒暄前缀
        _title_prefix_patterns = [
            r"^好的[,,].*?文章[::]\s*",
            r"^这是.{0,20}?标题[::]\s*",
        ]
        for pat in _title_prefix_patterns:
            m = re.match(pat, title)
            if m:
                title = title[m.end():].strip()
                break

        # 如果标题异常短或包含 LLM 输出痕迹,回退到原文标题
        if len(title) < 2 or "text" in title.lower() or "body" in title.lower():
            logger.warning(f"[RewriteProcessor] 标题解析异常,回退到原文: {title[:30]}")
            title = original_content.title

        # 提取摘要
        summary = ""
        if "【摘要】" in response or "摘要:" in response:
            summary_match = re.search(
                r"【摘要】[::]?\s*(.+?)(?:\n【|\n\n|$)",
                response,
                re.DOTALL
            )
            if summary_match:
                summary = summary_match.group(1).strip()

        # 提取正文
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

        content_text = content_text.strip()

        # 清理LLM常见的寒暄前缀
        import re as _re
        _prefix_patterns = [
            r'^好的[,,].{0,20}?[::]\s*',
            r'^好的[,,].{0,20}?[。.]\s*',
            r'^以下是.{0,20}?[::]\s*',
            r'^这是.{0,20}?[::]\s*',
            r'^好的[,。].*?文章[。]\s*',
        ]
        for pat in _prefix_patterns:
            m = _re.match(pat, content_text)
            if m:
                content_text = content_text[m.end():].strip()
                break

        # 提取关键词
        keywords = []
        if "【关键词】" in response or "关键词:" in response:
            kw_match = re.search(r"【关键词】[::]?\s*(.+?)(?:\n|$)", response)
            if kw_match:
                keywords = [k.strip() for k in kw_match.group(1).split(",")]

        # 元数据
        metadata = {
            "strategy": config.strategy.value,
            "original_length": len(original_content.content),
            "rewritten_length": len(content_text),
            "word_count": len(content_text),
            "rewritten": True,
            "translate_to": config.translate_to,
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
            summary=self._truncate(summary or content_text, 200),
            keywords=keywords,
            metadata=metadata
        )

    def _truncate(self, text: str, length: int) -> str:
        """截断文本"""
        if len(text) <= length:
            return text
        return text[:length] + "..."