"""Content Aggregator - Web GUI 入口

此模块保留向后兼容性。
推荐使用 web/server.py（完整版，7 页面，深色主题）。
启动方式：python scripts/web.py
"""

# 重导出完整版 app，确保 import content_aggregator.web 仍然可用
import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent.parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from web.server import app  # noqa: F401

__all__ = ["app"]
