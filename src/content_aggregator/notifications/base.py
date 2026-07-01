"""通知器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationResult:
    """通知发送结果"""
    success: bool
    notifier: str
    message: str = ""
    error: str = ""


@dataclass
class NotificationMessage:
    """通知消息"""
    title: str
    body: str
    level: str = "info"  # info / success / warning / error
    data: dict = field(default_factory=dict)
    articles_count: int = 0
    source_name: str = ""
    duration: float = 0.0


class BaseNotifier(ABC):
    """通知器基类"""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("enabled", True)

    @abstractmethod
    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送通知"""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """获取通知器名称"""
        ...

    async def notify(self, message: NotificationMessage) -> NotificationResult:
        """发送通知（带 enabled 检查）"""
        if not self.enabled:
            return NotificationResult(
                success=True,
                notifier=self.get_name(),
                message="通知器已禁用，跳过"
            )
        try:
            return await self.send(message)
        except Exception as e:
            return NotificationResult(
                success=False,
                notifier=self.get_name(),
                error=str(e)
            )
