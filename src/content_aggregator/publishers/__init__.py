"""
Publishers package for multi-platform publishing.
"""

from .wechat import WechatPublisher, WechatAPIError

__all__ = ["WechatPublisher", "WechatAPIError"]
