"""URL 内容采集服务 — httpx + trafilatura 实现"""

import logging

import httpx
import trafilatura

from app.core.exceptions import CollectError

logger = logging.getLogger(__name__)

# 常用请求头（模拟浏览器访问）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 采集超时（秒）
TIMEOUT = 15.0


async def collect_url(url: str) -> dict[str, str | int | None]:
    """从 URL 采集文章内容

    Args:
        url: 目标文章 URL

    Returns:
        dict 包含:
          - title: 文章标题
          - content: 正文内容（Markdown 格式）
          - author: 作者名（可能为 None）
          - word_count: 正文字数
          - source_url: 源 URL

    Raises:
        CollectError: 采集失败（网络错误、解析失败等）
    """
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=httpx.Timeout(TIMEOUT),
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as e:
        logger.warning(f"HTTP 请求失败: {url} — {e}")
        raise CollectError(f"无法访问该链接: {e}") from e

    # 使用 trafilatura 提取正文
    extracted = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        with_metadata=True,
    )

    if not extracted:
        raise CollectError("未能从该页面提取到正文内容，请确认链接是否正确")

    # trafilatura 提取结果可能包含元数据头
    # 分离元数据与正文
    metadata = trafilatura.extract_metadata(html)
    title = metadata.get("title") if metadata else None
    author = metadata.get("author") if metadata else None

    if not title:
        title = "未提取到标题"

    # 计算词数（中英文混合统计）
    word_count = _count_words(extracted)

    logger.info(f"采集成功: {url} — 标题={title}, 词数={word_count}")
    return {
        "title": title,
        "content": extracted,
        "author": author,
        "word_count": word_count,
        "source_url": url,
    }


def _count_words(text: str) -> int:
    """中英文混合词数统计

    - 英文：按空格分词
    - 中文：按字符计数（每个汉字算一个"词"）
    - 数字和标点不计数
    """
    import re
    # 匹配中文字符
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    # 匹配英文单词
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return chinese_chars + english_words
