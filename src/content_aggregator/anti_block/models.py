"""
防封采集 - 数据模型
"""
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime


class ProxyType(str, Enum):
    """代理类型"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class ProxyStatus(str, Enum):
    """代理状态"""
    AVAILABLE = "available"    # 可用
    BANNED = "banned"         # 被封
    TIMEOUT = "timeout"        # 超时
    INVALID = "invalid"        # 无效


class Proxy:
    """代理信息"""

    def __init__(
        self,
        ip: str,
        port: int,
        proxy_type: ProxyType = ProxyType.HTTP,
        username: Optional[str] = None,
        password: Optional[str] = None,
        source: str = "unknown",  # 来源（如：站大爷、自采）
    ):
        self.ip = ip
        self.port = port
        self.proxy_type = proxy_type
        self.username = username
        self.password = password
        self.source = source

        # 状态
        self.status = ProxyStatus.AVAILABLE
        self.last_used: Optional[datetime] = None
        self.success_count = 0
        self.fail_count = 0
        self.latency: Optional[float] = None  # 延迟（ms）

    @property
    def url(self) -> str:
        """代理 URL（供 requests 使用）"""
        if self.username and self.password:
            return f"{self.proxy_type.value}://{self.username}:{self.password}@{self.ip}:{self.port}"
        return f"{self.proxy_type.value}://{self.ip}:{self.port}"

    @property
    def dict(self) -> Dict[str, str]:
        """代理字典（供 requests 使用）"""
        return {
            "http": self.url,
            "https": self.url,
        }

    def mark_success(self):
        """标记成功"""
        self.success_count += 1
        self.last_used = datetime.now()
        self.status = ProxyStatus.AVAILABLE

    def mark_failure(self, reason: str = "unknown"):
        """标记失败"""
        self.fail_count += 1
        self.last_used = datetime.now()

        if reason in ("banned", "403", "429"):
            self.status = ProxyStatus.BANNED
        elif reason == "timeout":
            self.status = ProxyStatus.TIMEOUT
        else:
            self.status = ProxyStatus.INVALID

    def is_healthy(self, max_fail_rate: float = 0.5) -> bool:
        """判断是否健康（失败率 < max_fail_rate）"""
        total = self.success_count + self.fail_count
        if total == 0:
            return True
        fail_rate = self.fail_count / total
        return fail_rate < max_fail_rate and self.status != ProxyStatus.BANNED

    def __str__(self):
        return f"{self.proxy_type.value}://{self.ip}:{self.port} (status={self.status.value})"


class RequestConfig:
    """请求配置"""

    def __init__(
        self,
        min_delay: float = 1.0,
        max_delay: float = 3.0,
        timeout: int = 10,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0,
        user_agent_rotation: bool = True,
        referer_enabled: bool = True,
    ):
        """
        Args:
            min_delay: 最小延迟（秒）
            max_delay: 最大延迟（秒）
            timeout: 超时时间（秒）
            max_retries: 最大重试次数
            retry_backoff_factor: 重试退避因子（指数退避）
            user_agent_rotation: 是否轮换 User-Agent
            referer_enabled: 是否启用 Referer
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.user_agent_rotation = user_agent_rotation
        self.referer_enabled = referer_enabled


class BehaviorConfig:
    """行为模拟配置"""

    def __init__(
        self,
        enable_scroll: bool = True,
        scroll_min_time: float = 3.0,
        scroll_max_time: float = 10.0,
        enable_click: bool = False,
        click_probability: float = 0.3,
        enable_stay: bool = True,
        stay_min_time: float = 2.0,
        stay_max_time: float = 8.0,
    ):
        """
        Args:
            enable_scroll: 是否启用滑动模拟
            scroll_min_time: 最小滑动时间（秒）
            scroll_max_time: 最大滑动时间（秒）
            enable_click: 是否启用点击模拟
            click_probability: 点击概率（0~1）
            enable_stay: 是否启用停留模拟
            stay_min_time: 最小停留时间（秒）
            stay_max_time: 最大停留时间（秒）
        """
        self.enable_scroll = enable_scroll
        self.scroll_min_time = scroll_min_time
        self.scroll_max_time = scroll_max_time
        self.enable_click = enable_click
        self.click_probability = click_probability
        self.enable_stay = enable_stay
        self.stay_min_time = stay_min_time
        self.stay_max_time = stay_max_time
