"""
语言检测模块

功能：
1. 规则检测：通过 CJK 字符占比快速判断是否为中文
2. LLM 检测：规则无法确定时，使用 LLM 精确识别语言类型
3. 返回标准化语言代码（ISO 639-1）

使用示例：
    detector = LanguageDetector()
    result = await detector.detect("This is English text")
    # result = {"language": "en", "language_name": "英文", "method": "llm", "confidence": 0.95}
    
    result = await detector.detect("这是一段中文文本")
    # result = {"language": "zh", "language_name": "中文", "method": "rule", "confidence": 1.0}
"""

import json
import re
from typing import Any

import httpx
from loguru import logger

# CJK 统一表意文字范围
CJK_RANGES = [
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x2E80, 0x2EFF),    # CJK Radicals Supplement
    (0x3000, 0x303F),    # CJK Symbols and Punctuation
    (0x31C0, 0x31EF),    # CJK Strokes
    (0x2FF0, 0x2FFF),    # Ideographic Description Characters
    (0xFE30, 0xFE4F),    # CJK Compatibility Forms
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
]

# 日文特有字符范围（假名）
KANA_RANGES = [
    (0x3040, 0x309F),    # Hiragana
    (0x30A0, 0x30FF),    # Katakana
]

# 韩文特有字符范围
HANGUL_RANGES = [
    (0xAC00, 0xD7AF),    # Hangul Syllables
    (0x1100, 0x11FF),    # Hangul Jamo
]


def _char_in_ranges(char: str, ranges: list[tuple[int, int]]) -> bool:
    """检查字符是否在指定的 Unicode 范围内"""
    code = ord(char)
    for start, end in ranges:
        if start <= code <= end:
            return True
    return False


def _cjk_ratio(text: str) -> float:
    """计算 CJK 表意文字在文本中的占比"""
    if not text or not text.strip():
        return 0.0
    cjk_count = sum(1 for c in text if _char_in_ranges(c, CJK_RANGES))
    # 只计算非空白字符
    non_space = len(re.sub(r'\s', '', text))
    if non_space == 0:
        return 0.0
    return cjk_count / non_space


def _kana_ratio(text: str) -> float:
    """计算日文假名字符占比"""
    if not text or not text.strip():
        return 0.0
    kana_count = sum(1 for c in text if _char_in_ranges(c, KANA_RANGES))
    non_space = len(re.sub(r'\s', '', text))
    if non_space == 0:
        return 0.0
    return kana_count / non_space


def _hangul_ratio(text: str) -> float:
    """计算韩文字符占比"""
    if not text or not text.strip():
        return 0.0
    hangul_count = sum(1 for c in text if _char_in_ranges(c, HANGUL_RANGES))
    non_space = len(re.sub(r'\s', '', text))
    if non_space == 0:
        return 0.0
    return hangul_count / non_space


# 语言名称映射（ISO 639-1 → 中文名）
LANGUAGE_NAMES: dict[str, str] = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "fr": "法文",
    "de": "德文",
    "es": "西班牙文",
    "pt": "葡萄牙文",
    "ru": "俄文",
    "ar": "阿拉伯文",
    "it": "意大利文",
    "nl": "荷兰文",
    "sv": "瑞典文",
    "pl": "波兰文",
    "tr": "土耳其文",
    "th": "泰文",
    "vi": "越南文",
    "id": "印尼文",
    "ms": "马来文",
    "hi": "印地文",
}

# LLM 语言检测提示词
LANGUAGE_DETECTION_PROMPT = """请判断以下文本的主要语言。

输出格式（仅返回 JSON，不要任何额外文字）：
{"language": "<ISO-639-1 语言代码>", "language_name": "<中文语言名>", "confidence": <0.0~1.0 置信度>}

示例：
{"language": "en", "language_name": "英文", "confidence": 0.98}
{"language": "ja", "language_name": "日文", "confidence": 0.95}
{"language": "zh", "language_name": "中文", "confidence": 0.99}

文本内容：
"""


class LanguageDetectResult:
    """语言检测结果"""
    def __init__(
        self,
        language: str,
        language_name: str,
        method: str = "rule",
        confidence: float = 1.0,
    ):
        self.language = language
        self.language_name = language_name
        self.method = method          # "rule" | "llm"
        self.confidence = confidence

    def is_chinese(self) -> bool:
        """是否为中文"""
        return self.language == "zh"

    def needs_translation(self) -> bool:
        """是否需要翻译成中文"""
        return self.language not in ("zh", "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_name": self.language_name,
            "method": self.method,
            "confidence": self.confidence,
        }

    def __repr__(self) -> str:
        return f"<LanguageDetectResult {self.language_name}({self.language}) via {self.method} [{self.confidence:.0%}]>"


class LanguageDetector:
    """
    语言检测器

    检测策略：
    1. 规则检测（优先）：检查 CJK/假名/韩文字符占比
    2. LLM 检测（兜底）：规则无法判断时调用 LLM
    """

    def __init__(self, llm_config: dict[str, Any] | None = None):
        """
        初始化语言检测器

        Args:
            llm_config: LLM 配置（用于 LLM 兜底检测）
                - provider: LLM 供应商
                - api_key: API Key
                - model: 模型名
                - http_proxy: 代理地址（可选）
        """
        self.llm_config = llm_config or {}

    async def detect(self, text: str, title: str = "") -> LanguageDetectResult:
        """
        检测文本语言

        Args:
            text: 要检测的文本内容
            title: 文章标题（可选，用于辅助检测）

        Returns:
            LanguageDetectResult: 检测结果
        """
        if not text or len(text.strip()) < 20:
            return LanguageDetectResult("zh", "中文", "rule", 0.5)

        combined = f"{title}\n{text[:300]}" if title else text[:500]

        # 阶段 1：规则检测
        result = self._rule_detect(combined)
        if result is not None:
            return result

        # 阶段 2：LLM 兜底
        return await self._llm_detect(combined)

    def _rule_detect(self, text: str) -> LanguageDetectResult | None:
        """
        规则检测：通过字符范围判断

        Returns:
            确定时返回 LanguageDetectResult，不确定时返回 None
        """
        cjk = _cjk_ratio(text)
        kana = _kana_ratio(text)
        hangul = _hangul_ratio(text)

        logger.debug(
            f"[LanguageDetector._rule_detect] "
            f"CJK={cjk:.2%} Kana={kana:.2%} Hangul={hangul:.2%}"
        )

        # 中文：CJK字符占比 > 50%
        if cjk > 0.50:
            # 进一步区分中日韩
            if kana > 0.10 and cjk < 0.80:
                return LanguageDetectResult("ja", "日文", "rule", 0.9)
            if hangul > 0.10 and cjk < 0.80:
                return LanguageDetectResult("ko", "韩文", "rule", 0.9)
            return LanguageDetectResult("zh", "中文", "rule", min(0.95, cjk + 0.2))

        # 日文：假名占比 > 5%（可能是假名较多的日文文本）
        if kana > 0.05:
            return LanguageDetectResult("ja", "日文", "rule", 0.85)

        # 韩文：韩文占比 > 5%
        if hangul > 0.05:
            return LanguageDetectResult("ko", "韩文", "rule", 0.85)

        # 无法确定，需要 LLM 兜底
        return None

    async def _llm_detect(self, text: str) -> LanguageDetectResult:
        """
        LLM 检测：调用 LLM 识别语言
        """
        if not self.llm_config.get("api_key"):
            logger.warning("[LanguageDetector._llm_detect] LLM 未配置，回退为中文")
            return LanguageDetectResult("zh", "中文", "rule", 0.5)

        prompt = LANGUAGE_DETECTION_PROMPT + text[:2000]

        try:
            response = await self._call_llm(prompt)
            result = self._parse_llm_response(response)
            logger.info(
                f"[LanguageDetector._llm_detect] 检测结果: "
                f"{result.language_name}({result.language}) "
                f"conf={result.confidence:.0%}"
            )
            return result
        except Exception as e:
            logger.error(f"[LanguageDetector._llm_detect] LLM 检测失败: {e}")
            return LanguageDetectResult("zh", "中文", "rule", 0.5)

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        provider = self.llm_config.get("provider", "deepseek")
        api_key = self.llm_config["api_key"]
        model = self.llm_config.get("model", "deepseek-chat")

        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 100,
        }

        # 根据 provider 确定 API 地址
        base_urls = {
            "deepseek": "https://api.deepseek.com",
            "openai": "https://api.openai.com",
            "siliconflow": "https://api.siliconflow.cn",
        }
        base_url = base_urls.get(provider, "https://api.deepseek.com")

        proxy = self.llm_config.get("http_proxy", "")
        client_kwargs = {}
        if proxy:
            client_kwargs["proxies"] = {"http://": proxy, "https://": proxy}

        async with httpx.AsyncClient(**client_kwargs, timeout=10.0) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _parse_llm_response(self, response: str) -> LanguageDetectResult:
        """解析 LLM 返回的 JSON"""
        # 清理可能的 markdown 标记
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            match = re.search(r'\{[^{}]+\}', cleaned)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    data = {"language": "en", "language_name": "英文", "confidence": 0.5}
            else:
                data = {"language": "en", "language_name": "英文", "confidence": 0.5}

        language = data.get("language", "en")
        language_name = data.get("language_name", LANGUAGE_NAMES.get(language, language))
        confidence = min(1.0, max(0.0, float(data.get("confidence", 0.5))))

        return LanguageDetectResult(
            language=language,
            language_name=language_name,
            method="llm",
            confidence=confidence,
        )


def get_language_name(language_code: str) -> str:
    """获取语言代码对应的中文名称"""
    return LANGUAGE_NAMES.get(language_code, language_code)
