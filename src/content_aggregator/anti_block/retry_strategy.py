"""
防封采集 - 重试策略
支持指数退避、智能切换代理、自动降级
"""
import random
import time
from typing import Optional, Callable, Any, TypeVar, Generic
from enum import Enum
from datetime import datetime


T = TypeVar('T')


class RetryStrategy(str, Enum):
    """重试策略"""
    FIXED = "fixed"                  # 固定间隔
    EXPONENTIAL = "exponential"      # 指数退避
    LINEAR = "linear"                # 线性增长
    RANDOM = "random"                # 随机间隔


class RetryDecision(str, Enum):
    """重试决策"""
    RETRY = "retry"                  # 重试
    SWITCH_PROXY = "switch_proxy"    # 切换代理
    ABORT = "abort"                  # 放弃


def default_retry_condition(status_code: int) -> RetryDecision:
    """
    默认重试条件
    
    Args:
        status_code: HTTP状态码
        
    Returns:
        重试决策
    """
    if status_code in (403, 429):
        # IP被封/限流 → 切换代理
        return RetryDecision.SWITCH_PROXY
    elif status_code in (500, 502, 503, 504):
        # 服务器错误 → 重试
        return RetryDecision.RETRY
    elif status_code == 404:
        # 资源不存在 → 放弃
        return RetryDecision.ABORT
    else:
        return RetryDecision.RETRY


class RetryStrategyExecutor:
    """重试策略执行器"""

    def __init__(
        self,
        max_retries: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        retry_condition: Optional[Callable[[int], RetryDecision]] = None,
    ):
        """
        Args:
            max_retries: 最大重试次数
            strategy: 重试策略
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            backoff_factor: 退避因子
            jitter: 是否添加抖动（避免雷鸣群问题）
            retry_condition: 重试条件函数（根据状态码返回决策）
        """
        self.max_retries = max_retries
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.retry_condition = retry_condition or default_retry_condition

        self._retry_count = 0
        self._last_decision: Optional[RetryDecision] = None

    @property
    def retry_count(self) -> int:
        """已重试次数"""
        return self._retry_count

    @property
    def can_retry(self) -> bool:
        """是否可以继续重试"""
        return self._retry_count < self.max_retries

    def calculate_delay(self, attempt: int) -> float:
        """
        计算延迟时间
        
        Args:
            attempt: 第几次重试（从0开始）
        """
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.backoff_factor ** attempt)
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(self.base_delay, self.max_delay)
        else:
            delay = self.base_delay

        # 限制最大延迟
        delay = min(delay, self.max_delay)

        # 添加抖动
        if self.jitter:
            delay += random.uniform(0, delay * 0.1)

        return delay

    def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        执行函数（自动重试）
        
        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            Exception: 重试次数耗尽后抛出最后异常
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                self._retry_count = attempt
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # 判断是否应该重试
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    decision = self.retry_condition(status_code)
                else:
                    decision = RetryDecision.RETRY

                self._last_decision = decision

                if decision == RetryDecision.ABORT:
                    raise e

                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    time.sleep(delay)
                    continue

        # 重试次数耗尽
        raise last_exception

    async def execute_async(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        异步执行函数（自动重试）
        
        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                self._retry_count = attempt
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                # 判断是否应该重试
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    decision = self.retry_condition(status_code)
                else:
                    decision = RetryDecision.RETRY

                self._last_decision = decision

                if decision == RetryDecision.ABORT:
                    raise e

                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

        # 重试次数耗尽
        raise last_exception

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "retry_count": self._retry_count,
            "max_retries": self.max_retries,
            "strategy": self.strategy.value,
            "last_decision": self._last_decision.value if self._last_decision else None,
            "can_retry": self.can_retry,
        }

    def reset(self):
        """重置重试状态"""
        self._retry_count = 0
        self._last_decision = None
