"""通知模块

支持多种通知方式：
- Email（SMTP）
- Webhook（HTTP POST）
- 控制台输出（默认）
"""

from content_aggregator.notifications.base import BaseNotifier, NotificationResult, NotificationMessage
from content_aggregator.notifications.email_notifier import EmailNotifier
from content_aggregator.notifications.webhook_notifier import WebhookNotifier
from content_aggregator.notifications.console_notifier import ConsoleNotifier


def create_notifier(config: dict) -> BaseNotifier:
    """工厂方法：根据配置创建通知器"""
    notifier_type = config.get("type", "console")

    if notifier_type == "email":
        return EmailNotifier(config)
    elif notifier_type == "webhook":
        return WebhookNotifier(config)
    elif notifier_type == "console":
        return ConsoleNotifier(config)
    else:
        raise ValueError(f"不支持的通知类型: {notifier_type}，可选: email, webhook, console")


def create_notifiers(config: dict) -> list[BaseNotifier]:
    """根据配置创建所有通知器"""
    notifiers_cfg = config.get("notifications", {})
    if not notifiers_cfg:
        return [ConsoleNotifier({})]

    channels = notifiers_cfg.get("channels", [])
    if not channels:
        return [ConsoleNotifier({})]

    result = []
    for ch in channels:
        try:
            result.append(create_notifier(ch))
        except ValueError as e:
            import logging
            logging.getLogger(__name__).warning(f"跳过无效通知配置: {e}")

    return result if result else [ConsoleNotifier({})]


__all__ = [
    "BaseNotifier",
    "NotificationResult",
    "NotificationMessage",
    "EmailNotifier",
    "WebhookNotifier",
    "ConsoleNotifier",
    "create_notifier",
    "create_notifiers",
]
