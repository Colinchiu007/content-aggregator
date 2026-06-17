"""
LLM 响应处理工具集

从 Y2A-Auto 项目移植的经生产验证的 LLM 工具函数。
来源: github.com/fqscfqj/Y2A-Auto (modules/utils.py, modules/ai_enhancer.py)

功能：
1. 推理内容检测与剥离
2. 从任意 LLM 文本中提取 JSON
3. 输入内容预清洗（去噪/推广过滤）
4. 思考模式控制（尝试禁用 → 降级处理）

设计目标：
    消除 LLM 推理输出对改写/翻译的影响，提供统一的响应处理入口。
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ============================================================
# 1. 推理内容剥离
# ============================================================

# 预编译正则
_THINK_TAG_RE = re.compile(r"<\s*think\s*>.*?<\s*/\s*think\s*>", re.IGNORECASE | re.DOTALL)
_THINK_BLOCK_RE = re.compile(r"```\s*think[^\n]*\n.*?```", re.IGNORECASE | re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*|\s*```$", re.DOTALL)


def strip_reasoning_thoughts(text: str) -> str:
    """
    移除了思考模型产出的推理内容，仅保留最终答案。
    兼容:
    - DeepSeek 的 <think>...</think> 标签
    - ```think ...``` 代码块形式

    Returns:
        已移除推理内容的纯净文本
    """
    try:
        if not isinstance(text, str):
            return text

        cleaned = text

        # 移除 <think>...</think>（大小写不敏感，跨行匹配）
        cleaned = _THINK_TAG_RE.sub("", cleaned)

        # 移除 ```think ...``` 样式
        cleaned = _THINK_BLOCK_RE.sub("", cleaned)

        cleaned = cleaned.strip()
        return cleaned
    except Exception:
        return text


def strip_code_fences(text: str) -> str:
    """移除 Markdown 代码块围栏（```lang ... ```）"""
    try:
        if not isinstance(text, str):
            return text
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = _CODE_FENCE_RE.sub("", cleaned)
        return cleaned.strip()
    except Exception:
        return text


# ============================================================
# 2. JSON 提取
# ============================================================


def _extract_balanced_json_block(text: str, start_char: str, end_char: str) -> Optional[str]:
    """提取括号平衡的 JSON 块，兼容嵌套和字符串转义"""
    start = text.find(start_char)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == start_char:
            depth += 1
        elif char == end_char:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def extract_json_from_text(text: str, expected_type: Optional[type] = None) -> Optional[Any]:
    """
    从文本中提取 JSON，兼容 reasoning/代码块/其他包裹文本。

    Args:
        text: LLM 原始输出
        expected_type: 期望的 Python 类型 (dict/list)，None 不限制

    Returns:
        解析后的 Python 对象，失败返回 None

    示例:
        extract_json_from_text("```json\\n{\\"a\\": 1}\\n```") → {"a": 1}
        extract_json_from_text("Answer: [1, 2, 3]") → [1, 2, 3]
    """
    raw = strip_code_fences(strip_reasoning_thoughts(text)).strip() if text else ""
    if not raw:
        return None

    candidates = [raw]
    for start_char, end_char in (("{", "}"), ("[", "]")):
        block = _extract_balanced_json_block(raw, start_char, end_char)
        if block and block not in candidates:
            candidates.append(block)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if expected_type is not None and not isinstance(parsed, expected_type):
            continue
        return parsed
    return None


def get_chat_message_text(message) -> str:
    """
    提取 chat.completions message 的纯文本内容。
    兼容 content = None / list / str 以及 reasoning_content。

    Args:
        message: OpenAI chat.completion choice message 对象

    Returns:
        提取的纯文本，已剥离推理和代码块
    """
    if message is None:
        return ""

    content = getattr(message, "content", None)
    if isinstance(content, list):
        parts = []
        for segment in content:
            if isinstance(segment, dict):
                parts.append(str(segment.get("text", "")) if segment.get("text") else "")
            else:
                parts.append(str(getattr(segment, "text", "")))
        text = "".join(parts)
    else:
        text = str(content) if content else str(getattr(message, "reasoning_content", ""))

    return strip_code_fences(strip_reasoning_thoughts(text)).strip()


def extract_chat_message_json(message, expected_type: type = dict) -> Optional[Any]:
    """
    从 chat completion message 中提取 JSON。
    优先读取 message.parsed（结构化输出），失败时从文本中提取。

    Args:
        message: OpenAI chat.completion choice message 对象
        expected_type: 期望的 Python 类型 (默认 dict)

    Returns:
        解析后的 Python 对象，失败返回 None
    """
    # 优先使用结构化输出
    parsed = getattr(message, "parsed", None)
    if expected_type is None:
        if isinstance(parsed, (dict, list)):
            return parsed
    elif isinstance(parsed, expected_type):
        return parsed

    # 回退到文本提取
    return extract_json_from_text(get_chat_message_text(message), expected_type=expected_type)


# ============================================================
# 3. 输入内容预清洗（改写/翻译前）
# ============================================================

# URL 正则
_URL_PATTERNS = [
    re.compile(r"https?://[^\s\u4e00-\u9fff]+", re.IGNORECASE),
    re.compile(r"www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.IGNORECASE),
    re.compile(r"ftp://[^\s\u4e00-\u9fff]+", re.IGNORECASE),
]

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SOCIAL_HANDLE_RE = re.compile(r"@[A-Za-z0-9_]+")
_HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")

# 推广链接
_SPONSOR_URL_PATTERNS = [
    re.compile(r"patreon\.com/[^\s]*", re.IGNORECASE),
    re.compile(r"ko-fi\.com/[^\s]*", re.IGNORECASE),
    re.compile(r"buymeacoffee\.com/[^\s]*", re.IGNORECASE),
]

# CTA (Call To Action) 短语
_CTA_PATTERNS = [
    re.compile(r"link\s+in\s+[the\s]*description", re.IGNORECASE),
    re.compile(r"links?\s+[in\s]*[the\s]*bio", re.IGNORECASE),
    re.compile(r"check\s+[the\s]*description\s+for", re.IGNORECASE),
    re.compile(r"visit\s+[our\s]*website\s+at", re.IGNORECASE),
]

# 推广行模式
_PROMO_LINE_PATTERNS = [
    re.compile(r"^\s*video playlists?\s*:?", re.IGNORECASE),
    re.compile(r"^\s*all playlists?\s*:?", re.IGNORECASE),
    re.compile(r"^\s*website\s*:?", re.IGNORECASE),
    re.compile(r"^\s*official\s+site\s*:?", re.IGNORECASE),
    re.compile(r"^\s*(listen|watch)\s+to\s+", re.IGNORECASE),
    re.compile(r"^\s*(patreon|spotify|itunes|apple music|cdbaby)\b", re.IGNORECASE),
    re.compile(r"^\s*(follow|subscribe|like|share|download|buy)\b", re.IGNORECASE),
    re.compile(
        r"^\s*(播放列表|更多内容|关注|订阅|点赞|分享|评论区|下载链接|购买链接|联系方式)\s*[:：]?",
        re.IGNORECASE,
    ),
]

_INTERACTION_PATTERNS = [
    re.compile(r"订阅[我们的]*[频道]*"),
    re.compile(r"关注[我们]*"),
    re.compile(r"点赞[这个]*[视频]*"),
    re.compile(r"分享[给]*[朋友们]*"),
    re.compile(r"评论[区]*[见]*"),
    re.compile(r"更多[内容]*请访问"),
    re.compile(r"详情见[链接]*"),
    re.compile(r"链接在[描述]*[中]*"),
    re.compile(r"访问[我们的]*[网站]*"),
    re.compile(r"subscribe\s+to\s+[our\s]*channel", re.IGNORECASE),
    re.compile(r"follow\s+[us\s]*", re.IGNORECASE),
    re.compile(r"like\s+[this\s]*video", re.IGNORECASE),
    re.compile(r"share\s+[with\s]*[friends\s]*", re.IGNORECASE),
    re.compile(r"check\s+out\s+[our\s]*[websit\s]*", re.IGNORECASE),
]

_WHITESPACE_RE = re.compile(r"[ \t\f\v]+")
_TRAILING_SPACE_RE = re.compile(r"[ \t]+\n")
_MULTIPLE_NEWLINES_RE = re.compile(r"\n{3,}")


def _normalize_whitespace(text: str) -> str:
    """规范化空白字符"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    text = _TRAILING_SPACE_RE.sub("\n", text)
    text = _MULTIPLE_NEWLINES_RE.sub("\n\n", text)
    return text.strip()


def _looks_like_promo_line(line: str) -> bool:
    """判断一行是否是推广内容"""
    if not line:
        return False
    compact = line.strip()
    if not compact:
        return False
    # 含 ► 符号
    if "►" in compact:
        return True
    # 含 URL
    if _URL_PATTERNS[0].search(compact) or _URL_PATTERNS[1].search(compact):
        return True
    # 匹配推广行模式
    for pat in _PROMO_LINE_PATTERNS:
        if pat.search(compact):
            return True
    for pat in _CTA_PATTERNS:
        if pat.search(compact):
            return True
    return False


def clean_input_content(text: str, max_blocks: Optional[int] = 2) -> str:
    """
    对输入 LLM 的内容进行预清洗：去除推广信息、URL、等噪点。

    适用于：
    - 改写前的原文清洗
    - 翻译前的文本去噪
    - YouTube 描述清理后提交给 LLM

    Args:
        text: 原始内容
        max_blocks: 最多保留多少段（None 不限制）

    Returns:
        清洗后的内容
    """
    if not text:
        return ""

    # 1. 移除显式 URL/邮箱/社交账号/标签
    cleaned = text
    for pat in _URL_PATTERNS:
        cleaned = pat.sub("", cleaned)
    cleaned = _EMAIL_RE.sub("", cleaned)
    cleaned = _SOCIAL_HANDLE_RE.sub("", cleaned)
    cleaned = _HASHTAG_RE.sub("", cleaned)
    for pat in _SPONSOR_URL_PATTERNS:
        cleaned = pat.sub("", cleaned)
    for pat in _CTA_PATTERNS:
        cleaned = pat.sub("", cleaned)

    # 2. 按段拆分，过滤推广段
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", cleaned) if b and b.strip()]
    filtered = []
    for block in blocks:
        # 判断该段是否是推广内容
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        promo_lines = sum(1 for ln in lines if _looks_like_promo_line(ln))
        # 如果超过一半行是推广内容，跳过整段
        if promo_lines >= max(2, len(lines) // 2):
            continue

        # 过滤单行内的促销信息
        clean_lines = []
        for line in lines:
            if _looks_like_promo_line(line):
                continue
            # 移除文末的 CTA
            for pat in _INTERACTION_PATTERNS:
                line = pat.sub("", line)
            clean_lines.append(line)

        if clean_lines:
            filtered.append(" ".join(clean_lines))

    # 限制段数
    if max_blocks is not None:
        filtered = filtered[:max(max_blocks, 1)]

    return _normalize_whitespace("\n\n".join(filtered))


# ============================================================
# 4. 思考模式控制
# ============================================================


def build_thinking_disabled_body(body: dict) -> dict:
    """
    在请求体中添加 thinking 禁用参数（兼容 OpenAI / DeepSeek / SenseNova）。

    示例输入:
        {"model": "...", "messages": [...]}
    示例输出:
        {"model": "...", "messages": [...], "extra_body": {"thinking": {"type": "disabled"}}}

    Returns:
        修改后的请求体（不会污染原始 dict）
    """
    import copy

    new_body = copy.deepcopy(body)
    extra_body = new_body.setdefault("extra_body", {})
    thinking = extra_body.setdefault("thinking", {})
    if isinstance(thinking, dict):
        thinking["type"] = "disabled"
        thinking["enabled"] = False
    return new_body


# ============================================================
# 5. YouTube 错误诊断
# ============================================================


def looks_like_youtube_bot_challenge(error_text: Optional[str]) -> bool:
    """
    判断错误信息是否属于 YouTube 反机器人/登录校验问题。
    从 Y2A-Auto youtube_handler.py 移植。

    适用场景：
        YouTube Data API / yt-dlp 返回的错误文本
    """
    if not error_text:
        return False
    normalized = str(error_text)
    indicators = (
        "Sign in to confirm",
        "not a bot",
        "Signature extraction failed",
        "Some formats may be missing",
        "HTTP Error 403",
        "player",
        "decodeURIComponent",
        "The page needs to be reloaded.",
    )
    return any(indicator in normalized for indicator in indicators)


def looks_like_format_selection_error(error_text: Optional[str]) -> bool:
    """
    判断是否属于格式选择失败（而非视频不可访问）。
    从 Y2A-Auto youtube_handler.py 移植。
    """
    if not error_text:
        return False
    normalized = str(error_text)
    indicators = (
        "Requested format is not available",
        "Only images are available",
    )
    return any(indicator in normalized for indicator in indicators)


def summarize_yt_error(stdout_text: Optional[str], stderr_text: Optional[str]) -> str:
    """
    从 yt-dlp 输出中提取更有价值的错误摘要。
    从 Y2A-Auto youtube_handler.py 移植。
    """
    candidates: list[str] = []
    for text in (stderr_text, stdout_text):
        if not text:
            continue
        for raw_line in str(text).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("ERROR:"):
                candidates.append(line)
            elif "[youtube]" in line or "[download]" in line:
                candidates.append(line)

    if candidates:
        return candidates[-1]

    merged = (stderr_text or stdout_text or "").strip()
    if not merged:
        return "未知错误"

    lines = [line.strip() for line in merged.splitlines() if line.strip()]
    return lines[-1] if lines else "未知错误"
