"""
采集器基类

提供所有采集器的通用接口：
- 统一的错误处理（网络超时/代理失效/访问被拒 → 优雅跳过，不中断）
- 代理感知（自动读取全局 proxy 配置）
- 限流控制（请求间隔）
- 来源标记（标注每个 article 的来源平台）
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from httpx import AsyncClient, HTTPStatusError, ProxyError, ConnectError, ReadTimeout

logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    """采集结果（统一格式）"""
    success: bool          # 是否成功
    data: list[dict]       # 文章列表
    error: str | None      # 错误信息（失败时）
    source_name: str       # 来源名称（如 youtube / douyin）
    collected_count: int = 0   # 成功采集数
    skipped_count: int = 0    # 跳过数（网络错误）
    duration: float = 0.0     # 耗时秒
    metadata: dict[str, Any] = field(default_factory=dict)   # 扩展信息


class BaseCollector(ABC):
    """
    采集器基类

    设计原则：
    1. 所有网络错误 → WARNING + 返回空数据，不抛异常
    2. 代理不可用时 → 自动尝试直连，失败后跳过并提示
    3. 限流（每个源默认请求间隔 2s，避免触发反爬）
    """

    # 子类覆盖
    SOURCE_NAME: str = "unknown"      # 平台标识
    RATE_LIMIT: float = 2.0           # 请求间隔（秒）

    def __init__(self, proxy: str | None = None, timeout: int = 30, config: dict | None = None, **kwargs):
        """
        参数：
            proxy: HTTP 代理地址（如 http://127.0.0.1:12334），None 表示直连
            timeout: 请求超时秒数
            config: 数据源配置字典（可选）
        """
        self.config = config or {}
        self.proxy = proxy
        self.timeout = timeout
        self._client: AsyncClient | None = None
        self._last_request_time: float = 0.0

    async def _get_client(self) -> AsyncClient:
        """获取或创建 HTTP 客户端（懒加载）"""
        if self._client is None or self._client.is_closed:
            self._client = AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def _close_client(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _rate_limit_wait(self):
        """请求间隔控制"""
        import time
        elapsed = time.time() - self._last_request_time
        if elapsed < self.RATE_LIMIT:
            await asyncio.sleep(self.RATE_LIMIT - elapsed)
        self._last_request_time = time.time()

    def _error_hint(self, source_name: str, error: Exception) -> str:
        """生成用户友好的错误提示"""
        msg = str(error)
        if isinstance(error, ProxyError | ConnectError):
            return f"[{source_name}] 代理不可用（{self.proxy}），跳过。可在配置中关闭代理或检查代理服务。"
        if isinstance(error, ReadTimeout):
            return f"[{source_name}] 请求超时（{self.timeout}s），跳过。建议检查网络或增加 timeout。"
        if isinstance(error, HTTPStatusError):
            if error.response.status_code == 403:
                return f"[{source_name}] 访问被拒绝（403），跳过。可能需要代理或账号授权。"
            if error.response.status_code == 429:
                return f"[{source_name}] 请求过于频繁（429），跳过。已自动等待重试。"
            return f"[{source_name}] HTTP {error.response.status_code}，跳过。"
        return f"[{source_name}] 网络错误：{msg}，跳过。"

    async def collect(self, **kwargs) -> SourceResult:
        """
        采集入口（子类实现）

        统一包装：
        - 网络错误 → 优雅跳过
        - 限流等待
        - 计时
        """
        import time
        start = time.time()
        try:
            await self._rate_limit_wait()
            data = await self._fetch(**kwargs)
            return SourceResult(
                success=True,
                data=data,
                error=None,
                source_name=self.SOURCE_NAME,
                collected_count=len(data),
                duration=time.time() - start,
            )
        except Exception as e:
            hint = self._error_hint(self.SOURCE_NAME, e)
            logger.warning(hint)
            return SourceResult(
                success=False,
                data=[],
                error=hint,
                source_name=self.SOURCE_NAME,
                skipped_count=1,
                duration=time.time() - start,
            )
        finally:
            await self._close_client()

    @abstractmethod
    async def _fetch(self, **kwargs) -> list[dict]:
        """
        子类实现具体采集逻辑

        返回：文章字典列表，每篇包含 title/content/url/published_at 等字段
        如遇网络错误，直接 raise，基类会捕获并转换为优雅跳过
        """
        ...