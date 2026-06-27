"""Webhook 通知器

发送 HTTP POST 请求到指定 URL，支持：
- 自定义 Header
- JSON payload
- 重试机制
"""

import httpx
from loguru import logger

from content_aggregator.notifications.base import (
    BaseNotifier,
    NotificationMessage,
    NotificationResult,
)


class WebhookNotifier(BaseNotifier):
    """Webhook 通知器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.url = config.get("url", "")
        self.method = config.get("method", "POST").upper()
        self.headers = config.get("headers", {"Content-Type": "application/json"})
        self.timeout = config.get("timeout", 10)

    def get_name(self) -> str:
        return f"WebhookNotifier({self.url[:50]})"

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送 Webhook 通知"""
        if not self.url:
            return NotificationResult(
                success=False,
                notifier=self.get_name(),
                error="Webhook URL 未配置"
            )

        payload = {
            "title": message.title,
            "body": message.body,
            "level": message.level,
            "source_name": message.source_name,
            "articles_count": message.articles_count,
            "duration": message.duration,
            "data": message.data,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(
                    self.method,
                    self.url,
                    json=payload,
                    headers=self.headers,
                )

                if resp.status_code < 400:
                    logger.info(f"Webhook 通知已发送: {self.url} (status={resp.status_code})")
                    return NotificationResult(
                        success=True,
                        notifier=self.get_name(),
                        message=f"HTTP {resp.status_code}"
                    )
                else:
                    return NotificationResult(
                        success=False,
                        notifier=self.get_name(),
                        error=f"HTTP {resp.status_code}: {resp.text[:200]}"
                    )
        except Exception as e:
            logger.error(f"Webhook 通知失败: {e}")
            return NotificationResult(
                success=False,
                notifier=self.get_name(),
                error=str(e)
            )
