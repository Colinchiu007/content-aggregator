"""控制台通知器

输出到标准输出/日志，作为默认通知方式。
"""

from loguru import logger

from content_aggregator.notifications.base import (
    BaseNotifier,
    NotificationMessage,
    NotificationResult,
)


class ConsoleNotifier(BaseNotifier):
    """控制台通知器"""

    def __init__(self, config: dict):
        super().__init__(config)

    def get_name(self) -> str:
        return "ConsoleNotifier"

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """输出通知到控制台"""
        level_icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
        }
        icon = level_icons.get(message.level, "📢")

        logger.info(
            f"{icon} [通知] {message.title} | "
            f"来源={message.source_name or 'N/A'} | "
            f"文章数={message.articles_count} | "
            f"耗时={message.duration:.1f}s"
        )
        if message.body:
            for line in message.body.split("\n")[:5]:
                logger.info(f"  {line}")

        return NotificationResult(
            success=True,
            notifier=self.get_name(),
            message="已输出到控制台"
        )
