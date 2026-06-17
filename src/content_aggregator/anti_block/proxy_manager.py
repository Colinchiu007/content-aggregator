"""
防封采集 - 代理池管理器
"""
import random
import time
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import requests

from .models import Proxy, ProxyStatus, ProxyType


class ProxyManager:
    """代理池管理器"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_pool_size: int = 100,
        health_check_interval: int = 300,  # 5 minutes
        max_fail_rate: float = 0.5,
    ):
        """
        Args:
            api_url: 代理API地址（如：站大爷）
            api_key: API密钥
            max_pool_size: 代理池最大大小
            health_check_interval: 健康检查间隔（秒）
            max_fail_rate: 最大失败率（超过则移除）
        """
        self.api_url = api_url
        self.api_key = api_key
        self.max_pool_size = max_pool_size
        self.health_check_interval = health_check_interval
        self.max_fail_rate = max_fail_rate

        self._pool: List[Proxy] = []
        self._last_health_check: Optional[datetime] = None

    @property
    def pool_size(self) -> int:
        """代理池大小"""
        return len(self._pool)

    @property
    def available_count(self) -> int:
        """可用代理数量"""
        return sum(1 for p in self._pool if p.status == ProxyStatus.AVAILABLE)

    def add_proxy(self, proxy: Proxy) -> bool:
        """添加代理到池"""
        if self.pool_size >= self.max_pool_size:
            # 移除最不健康的代理
            self._remove_unhealthy()
            if self.pool_size >= self.max_pool_size:
                return False

        self._pool.append(proxy)
        return True

    def get_proxy(self, healthy_only: bool = True) -> Optional[Proxy]:
        """获取一个代理（优先返回最健康的）"""
        candidates = [p for p in self._pool if p.is_healthy(self.max_fail_rate)]
        
        if not candidates:
            # 池为空或所有代理都不健康，尝试从API获取
            self._fetch_from_api()
            candidates = [p for p in self._pool if p.is_healthy(self.max_fail_rate)]
        
        if not candidates:
            return None
        
        # 优先返回最近未使用的、延迟最低的
        candidates.sort(key=lambda p: (p.last_used or datetime.min, p.latency or 999999))
        return candidates[0]

    def mark_success(self, proxy: Proxy):
        """标记代理成功"""
        proxy.mark_success()
        self._check_health()

    def mark_failure(self, proxy: Proxy, reason: str = "unknown"):
        """标记代理失败"""
        proxy.mark_failure(reason)
        self._check_health()

    def remove_proxy(self, proxy: Proxy) -> bool:
        """移除代理"""
        if proxy in self._pool:
            self._pool.remove(proxy)
            return True
        return False

    def _remove_unhealthy(self):
        """移除不健康的代理"""
        self._pool = [p for p in self._pool if p.is_healthy(self.max_fail_rate)]

    def _check_health(self):
        """定期检查代理健康状态"""
        now = datetime.now()
        if (self._last_health_check is None or 
            (now - self._last_health_check).seconds > self.health_check_interval):
            self._remove_unhealthy()
            self._last_health_check = now

    def _fetch_from_api(self, count: int = 10) -> int:
        """从API获取代理"""
        if not self.api_url or not self.api_key:
            return 0

        try:
            url = f"{self.api_url}?count={count}&type=json&key={self.api_key}"
            resp = requests.get(url, timeout=10)
            data = resp.json()

            if data.get("code") == 0:
                added = 0
                for item in data.get("data", []):
                    proxy = Proxy(
                        ip=item["ip"],
                        port=item["port"],
                        proxy_type=ProxyType.HTTP,
                        source=self.api_url,
                    )
                    if self.add_proxy(proxy):
                        added += 1
                return added
            return 0
        except Exception as e:
            print(f"[ProxyManager] API获取代理失败: {e}")
            return 0

    def validate_proxy(self, proxy: Proxy, test_url: str = "http://httpbin.org/ip") -> bool:
        """验证代理是否可用"""
        try:
            resp = requests.get(
                test_url,
                proxies=proxy.dict,
                timeout=10,
            )
            if resp.status_code == 200:
                proxy.mark_success()
                return True
        except Exception:
            pass
        
        proxy.mark_failure("timeout")
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total": self.pool_size,
            "available": self.available_count,
            "banned": sum(1 for p in self._pool if p.status == ProxyStatus.BANNED),
            "timeout": sum(1 for p in self._pool if p.status == ProxyStatus.TIMEOUT),
            "invalid": sum(1 for p in self._pool if p.status == ProxyStatus.INVALID),
        }

    def clear(self):
        """清空代理池"""
        self._pool.clear()
        self._last_health_check = None
