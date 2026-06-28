"""
数据源基类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SourceConfig:
    """数据源配置"""
    id: str
    name: str
    source_type: str
    config: dict[str, Any]


@dataclass
class TestResult:
    """数据源测试结果"""
    success: bool
    message: str
    details: dict[str, Any] | None = None


class BaseSource(ABC):
    """数据源基类"""

    def __init__(self, config: SourceConfig):
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """连接数据源"""
        pass

    @abstractmethod
    async def collect(self, filters: dict[str, Any] | None = None) -> dict:
        """采集内容"""
        pass

    @abstractmethod
    async def test(self) -> TestResult:
        """测试数据源"""
        pass