"""
防封采集 - 请求调度器
"""
import random
import time
from typing import Optional, Callable, Any
from datetime import datetime
import asyncio


class RequestScheduler:
    """请求调度器（频率限制 + 随机延迟）"""

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        max_requests_per_minute: int = 20,
    ):
        """
        Args:
            min_delay: 最小延迟（秒）
            max_delay: 最大延迟（秒）
            max_requests_per_minute: 每分钟最大请求数
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_requests_per_minute = max_requests_per_minute

        self._request_history: list[datetime] = []
        self._last_request_time: Optional[datetime] = None

    def wait(self):
        """等待合适的请求时机"""
        now = datetime.now()

        # 1. 随机延迟（模拟真人）
        delay = random.uniform(self.min_delay, self.max_delay)
        
        # 2. 检查频率限制
        if self._last_request_time:
            elapsed = (now - self._last_request_time).total_seconds()
            if elapsed < self.min_delay:
                delay = max(delay, self.min_delay - elapsed)

        # 3. 检查每分钟请求数
        self._clean_history(now)
        if len(self._request_history) >= self.max_requests_per_minute:
            # 需要等待更长时间
            oldest = self._request_history[0]
            wait_time = 60 - (now - oldest).total_seconds()
            if wait_time > 0:
                delay = max(delay, wait_time)

        # 4. 执行等待
        if delay > 0:
            time.sleep(delay)

        # 5. 记录请求
        self._last_request_time = datetime.now()
        self._request_history.append(self._last_request_time)

    def _clean_history(self, now: datetime):
        """清理超过1分钟的请求记录"""
        cutoff = now.timestamp() - 60
        self._request_history = [
            t for t in self._request_history 
            if t.timestamp() > cutoff
        ]

    async def wait_async(self):
        """异步等待（用于 async/await）"""
        now = datetime.now()
        delay = random.uniform(self.min_delay, self.max_delay)

        if self._last_request_time:
            elapsed = (now - self._last_request_time).total_seconds()
            if elapsed < self.min_delay:
                delay = max(delay, self.min_delay - elapsed)

        self._clean_history(now)
        if len(self._request_history) >= self.max_requests_per_minute:
            oldest = self._request_history[0]
            wait_time = 60 - (now - oldest).total_seconds()
            if wait_time > 0:
                delay = max(delay, wait_time)

        if delay > 0:
            await asyncio.sleep(delay)

        self._last_request_time = datetime.now()
        self._request_history.append(self._last_request_time)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "total_requests": len(self._request_history),
            "requests_last_minute": len(self._request_history),
            "min_delay": self.min_delay,
            "max_delay": self.max_delay,
            "max_requests_per_minute": self.max_requests_per_minute,
        }
