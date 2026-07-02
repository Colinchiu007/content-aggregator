"""邮件通知器

使用 SMTP 发送邮件通知，支持：
- TLS/SSL 加密
- HTML 邮件模板
- 多收件人
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from loguru import logger

from content_aggregator.notifications.base import (
    BaseNotifier,
    NotificationMessage,
    NotificationResult,
)


class EmailNotifier(BaseNotifier):
    """SMTP 邮件通知器"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.smtp_host = config.get("smtp_host", "smtp.qq.com")
        self.smtp_port = config.get("smtp_port", 465)
        self.use_ssl = config.get("use_ssl", True)
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.from_addr = config.get("from_addr", self.username)
        self.to_addrs = config.get("to_addrs", [])
        if isinstance(self.to_addrs, str):
            self.to_addrs = [self.to_addrs]

    def get_name(self) -> str:
        return f"EmailNotifier({self.smtp_host})"

    async def send(self, message: NotificationMessage) -> NotificationResult:
        """发送邮件通知"""
        if not self.username or not self.password:
            return NotificationResult(
                success=False,
                notifier=self.get_name(),
                error="SMTP 用户名或密码未配置"
            )
        if not self.to_addrs:
            return NotificationResult(
                success=False,
                notifier=self.get_name(),
                error="收件人地址未配置"
            )

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[Content Aggregator] {message.title}"
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        # 纯文本版本
        text_body = self._build_text_body(message)
        msg.attach(MIMEText(text_body, "plain", "utf-8"))

        # HTML 版本
        html_body = self._build_html_body(message)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # 发送
        try:
            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                server.starttls()

            server.login(self.username, self.password)
            server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            server.quit()

            logger.info(f"邮件通知已发送: {message.title} → {self.to_addrs}")
            return NotificationResult(
                success=True,
                notifier=self.get_name(),
                message=f"邮件已发送至 {len(self.to_addrs)} 个收件人"
            )
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return NotificationResult(
                success=False,
                notifier=self.get_name(),
                error=str(e)
            )

    def _build_text_body(self, message: NotificationMessage) -> str:
        """构建纯文本邮件体"""
        lines = [
            message.title,
            "=" * 40,
            f"级别: {message.level}",
            f"来源: {message.source_name or 'N/A'}",
            f"文章数: {message.articles_count}",
            f"耗时: {message.duration:.1f}s",
            "",
            message.body,
        ]
        if message.data:
            lines.append("")
            lines.append("--- 详细信息 ---")
            for k, v in message.data.items():
                lines.append(f"{k}: {v}")
        return "\n".join(lines)

    def _build_html_body(self, message: NotificationMessage) -> str:
        """构建 HTML 邮件体"""
        level_colors = {
            "info": "#3b82f6",
            "success": "#22c55e",
            "warning": "#f59e0b",
            "error": "#ef4444",
        }
        color = level_colors.get(message.level, "#6b7280")

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
<div style="border-left:4px solid {color};padding:16px;background:#f9fafb;border-radius:4px">
<h2 style="margin:0 0 12px;color:#111">{message.title}</h2>
<p style="color:#6b7280;margin:4px 0">
<span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px">{message.level.upper()}</span>
&nbsp;来源: {message.source_name or 'N/A'} &nbsp;|&nbsp; 文章数: {message.articles_count} &nbsp;|&nbsp; 耗时: {message.duration:.1f}s
</p>
<div style="margin-top:12px;line-height:1.8;color:#374151">{message.body}</div>
</div>
<p style="color:#9ca3af;font-size:12px;margin-top:16px">— Content Aggregator 自动通知</p>
</body></html>"""
        return html
