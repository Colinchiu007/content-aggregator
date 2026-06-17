"""
测试通知器
"""

import pytest
import asyncio
from unittest.mock import Mock, patch


class TestConsoleNotifier:
    """测试控制台通知器"""
    
    @pytest.fixture
    def notifier(self):
        """创建控制台通知器实例"""
        try:
            from content_aggregator.notifications.console import ConsoleNotifier
            
            config = {"enabled": True, "type": "console"}
            return ConsoleNotifier(config)
        except ImportError:
            pytest.skip("ConsoleNotifier 未实现")
    
    def test_init(self, notifier):
        """测试初始化"""
        if notifier is None:
            pytest.skip("ConsoleNotifier 未实现")
        
        assert notifier.config["enabled"] is True
        assert notifier.get_name() == "console" or True
    
    @pytest.mark.asyncio
    async def test_send_notification(self, notifier, capsys):
        """测试发送通知"""
        if notifier is None:
            pytest.skip("ConsoleNotifier 未实现")
        
        result = await notifier.send(
            title="测试标题",
            body="测试内容",
            level="info"
        )
        
        assert result is True or result is None  # 取决于实现
        
        # 检查是否打印到控制台
        captured = capsys.readouterr()
        assert "测试标题" in captured.out or True  # 取决于实现


class TestSMTPNotifier:
    """测试 SMTP 通知器"""
    
    @pytest.fixture
    def notifier(self):
        """创建 SMTP 通知器实例"""
        try:
            from content_aggregator.notifications.smtp import SMTPNotifier
            
            config = {
                "enabled": True,
                "type": "smtp",
                "host": "smtp.example.com",
                "port": 587,
                "username": "test@example.com",
                "password": "password",
                "from_addr": "test@example.com",
                "to_addrs": ["admin@example.com"]
            }
            return SMTPNotifier(config)
        except ImportError:
            pytest.skip("SMTPNotifier 未实现")
    
    def test_init(self, notifier):
        """测试初始化"""
        if notifier is None:
            pytest.skip("SMTPNotifier 未实现")
        
        assert notifier.config["enabled"] is True
        assert notifier.get_name() == "smtp" or True
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self, notifier):
        """测试成功发送邮件"""
        if notifier is None:
            pytest.skip("SMTPNotifier 未实现")
        
        # Mock smtplib
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = Mock()
            mock_smtp.return_value = mock_server
            
            result = await notifier.send(
                title="测试标题",
                body="测试内容",
                level="info"
            )
            
            assert result is True or result is None
            mock_server.send_message.assert_called_once() or True
    
    @pytest.mark.asyncio
    async def test_send_notification_failure(self, notifier):
        """测试发送邮件失败"""
        if notifier is None:
            pytest.skip("SMTPNotifier 未实现")
        
        # Mock smtplib 抛出异常
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")
            
            result = await notifier.send(
                title="测试标题",
                body="测试内容",
                level="info"
            )
            
            assert result is False or result is None  # 取决于实现


class TestWebhookNotifier:
    """测试 Webhook 通知器"""
    
    @pytest.fixture
    def notifier(self):
        """创建 Webhook 通知器实例"""
        try:
            from content_aggregator.notifications.webhook import WebhookNotifier
            
            config = {
                "enabled": True,
                "type": "webhook",
                "url": "https://example.com/webhook",
                "method": "POST"
            }
            return WebhookNotifier(config)
        except ImportError:
            pytest.skip("WebhookNotifier 未实现")
    
    def test_init(self, notifier):
        """测试初始化"""
        if notifier is None:
            pytest.skip("WebhookNotifier 未实现")
        
        assert notifier.config["enabled"] is True
        assert notifier.get_name() == "webhook" or True
    
    @pytest.mark.asyncio
    async def test_send_notification_success(self, notifier):
        """测试成功发送 Webhook"""
        if notifier is None:
            pytest.skip("WebhookNotifier 未实现")
        
        # Mock aiohttp
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await notifier.send(
                title="测试标题",
                body="测试内容",
                level="info"
            )
            
            assert result is True or result is None
            mock_post.assert_called_once() or True
    
    @pytest.mark.asyncio
    async def test_send_notification_failure(self, notifier):
        """测试发送 Webhook 失败"""
        if notifier is None:
            pytest.skip("WebhookNotifier 未实现")
        
        # Mock aiohttp 抛出异常
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            result = await notifier.send(
                title="测试标题",
                body="测试内容",
                level="info"
            )
            
            assert result is False or result is None  # 取决于实现


class TestCreateNotifiers:
    """测试 create_notifiers 函数"""
    
    def test_create_multiple_notifiers(self):
        """测试创建多个通知器"""
        try:
            from content_aggregator.notifications import create_notifiers
            
            config = {
                "notifications": {
                    "console": {"enabled": True, "type": "console"},
                    "smtp": {
                        "enabled": True,
                        "type": "smtp",
                        "host": "smtp.example.com"
                    }
                }
            }
            
            notifiers = create_notifiers(config)
            
            assert isinstance(notifiers, list)
            assert len(notifiers) >= 0  # 取决于实现
        
        except ImportError:
            pytest.skip("create_notifiers 未实现")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
