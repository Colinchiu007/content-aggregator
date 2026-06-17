"""
单元测试配置文件
"""
import sys
from pathlib import Path

# 添加项目 src 目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

import pytest

# 配置 pytest
pytest_plugins = []
