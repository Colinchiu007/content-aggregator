"""
防封采集 - 核心管理器
整合代理池、请求调度、行为模拟、重试策略
"""
import random
import time
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
from enum import Enum
import requests
from datetime import datetime

from .models import Proxy, ProxyStatus, RequestConfig, BehaviorConfig
from .proxy_manager import ProxyManager
from .request_scheduler import RequestScheduler
from .behavior_simulator import BehaviorSimulator
from .retry_strategy import RetryStrategyExecutor, RetryDecision


T = TypeVar('T')


class AntiBlockManager:
    """防封采集核心管理器"""

    def __init__(
        self,
        proxy_manager: Optional[ProxyManager] = None,
        request_config: Optional[RequestConfig] = None,
        behavior_config: Optional[BehaviorConfig] = None,
        retry_executor: Optional[RetryStrategyExecutor] = None,
    ):
        """
        初始化防封管理器
        
        Args:
            proxy_manager: 代理池管理器
            request_config: 请求配置
            behavior_config: 行为模拟配置
            retry_executor: 重试策略执行器
        """
        self.proxy_manager = proxy_manager
        self.request_config = request_config or RequestConfig()
        self.behavior_config = behavior_config or BehaviorConfig()
        
        # 初始化子模块
        self._request_scheduler = RequestScheduler(
            min_delay=self.request_config.min_delay,
            max_delay=self.request_config.max_delay,
            max_requests_per_minute=20,  # 默认每分钟20次
        )
        
        self._behavior_simulator = BehaviorSimulator(
            enable_stay=self.behavior_config.enable_stay,
            stay_min_time=self.behavior_config.stay_min_time,
            stay_max_time=self.behavior_config.stay_max_time,
            enable_scroll=self.behavior_config.enable_scroll,
            scroll_min_time=self.behavior_config.scroll_min_time,
            scroll_max_time=self.behavior_config.scroll_max_time,
        )
        
        self._retry_executor = retry_executor or RetryStrategyExecutor()
        
        # 统计信息
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._proxy_switches = 0

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = 10,
        **kwargs
    ) -> requests.Response:
        """
        发送HTTP请求（自动防封处理）
        
        Args:
            method: HTTP方法（GET/POST/PUT/DELETE）
            url: 请求URL
            headers: 请求头
            params: 查询参数
            data: 表单数据
            json: JSON数据
            timeout: 超时时间（秒）
            **kwargs: 其他requests参数
            
        Returns:
            Response对象
            
        Raises:
            Exception: 请求失败且重试次数耗尽
        """
        self._total_requests += 1
        
        # 1. 获取代理
        proxy = None
        if self.proxy_manager:
            proxy = self.proxy_manager.get_proxy()
            if proxy:
                kwargs['proxies'] = proxy.dict
        
        # 2. 请求调度（频率限制 + 随机延迟）
        self._request_scheduler.wait()
        
        # 3. 构建请求头（模拟浏览器）
        if headers is None:
            headers = {}
        
        # 添加基础请求头
        headers.update(self._behavior_simulator.get_behavior_headers())
        
        # 4. 执行请求（带重试）
        def _do_request():
            resp = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json,
                timeout=timeout,
                **kwargs
            )
            
            # 检查状态码
            if resp.status_code in (403, 429):
                # IP被封/限流 → 切换代理
                if proxy:
                    self.proxy_manager.mark_failure(proxy, "banned")
                    self._proxy_switches += 1
                raise requests.exceptions.HTTPError(f"Status {resp.status_code}", response=resp)
            
            resp.raise_for_status()
            return resp
        
        try:
            response = self._retry_executor.execute(_do_request)
            self._successful_requests += 1
            
            # 标记代理成功
            if proxy:
                self.proxy_manager.mark_success(proxy)
            
            # 5. 行为模拟（请求后）
            if self.behavior_config.enable_stay:
                self._behavior_simulator.simulate_stay()
            
            return response
            
        except Exception as e:
            self._failed_requests += 1
            raise

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """GET请求（自动防封）"""
        return self.request("GET", url, headers, params, **kwargs)

    def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """POST请求（自动防封）"""
        return self.request("POST", url, headers, data=data, json=json, **kwargs)

    def put(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """PUT请求（自动防封）"""
        return self.request("PUT", url, headers, data=data, json=json, **kwargs)

    def delete(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> requests.Response:
        """DELETE请求（自动防封）"""
        return self.request("DELETE", url, headers, **kwargs)

    def simulate_page_view(self, page_type: str = "detail") -> Dict[str, Any]:
        """
        模拟页面浏览（综合行为）
        
        Args:
            page_type: 页面类型（search/list/detail）
            
        Returns:
            行为模拟结果
        """
        return self._behavior_simulator.simulate_page_view(page_type)

    def switch_proxy(self) -> bool:
        """
        手动切换代理
        
        Returns:
            是否成功切换
        """
        if not self.proxy_manager:
            return False
        
        old_proxy = self.proxy_manager.get_proxy()
        if old_proxy:
            self.proxy_manager.mark_failure(old_proxy, "manual_switch")
        
        new_proxy = self.proxy_manager.get_proxy()
        if new_proxy and new_proxy != old_proxy:
            self._proxy_switches += 1
            return True
        
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "proxy_switches": self._proxy_switches,
            "success_rate": (
                self._successful_requests / self._total_requests
                if self._total_requests > 0 else 0
            ),
        }
        
        # 添加各子模块统计
        if self.proxy_manager:
            stats["proxy_pool"] = self.proxy_manager.get_stats()
        
        stats["request_scheduler"] = self._request_scheduler.get_stats()
        stats["retry_strategy"] = self._retry_executor.get_stats()
        
        return stats

    def reset(self):
        """重置所有状态"""
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._proxy_switches = 0
        
        if self.proxy_manager:
            self.proxy_manager.clear()
        
        self._retry_executor.reset()

    def set_proxy_api(
        self,
        api_url: str,
        api_key: str,
        max_pool_size: int = 100,
    ):
        """
        设置代理API（动态获取代理）
        
        Args:
            api_url: 代理API地址
            api_key: API密钥
            max_pool_size: 代理池最大大小
        """
        self.proxy_manager = ProxyManager(
            api_url=api_url,
            api_key=api_key,
            max_pool_size=max_pool_size,
        )

    def add_custom_proxy(
        self,
        ip: str,
        port: int,
        proxy_type: str = "http",
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """
        添加自定义代理
        
        Args:
            ip: 代理IP
            port: 代理端口
            proxy_type: 代理类型（http/https/socks5）
            username: 用户名（可选）
            password: 密码（可选）
            
        Returns:
            是否添加成功
        """
        if not self.proxy_manager:
            self.proxy_manager = ProxyManager()
        
        from .models import ProxyType
        proxy = Proxy(
            ip=ip,
            port=port,
            proxy_type=ProxyType(proxy_type),
            username=username,
            password=password,
        )
        
        return self.proxy_manager.add_proxy(proxy)
