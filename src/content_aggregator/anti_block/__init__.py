"""
防封采集模块 - 通用防封机制
支持小红书、抖音、公众号等多个平台
"""
from .models import Proxy, ProxyStatus, ProxyType, RequestConfig, BehaviorConfig
from .proxy_manager import ProxyManager
from .request_scheduler import RequestScheduler
from .behavior_simulator import BehaviorSimulator, InteractionType
from .retry_strategy import RetryStrategy, RetryDecision, RetryStrategyExecutor
from .anti_block_manager import AntiBlockManager

__all__ = [
    # 核心管理器
    "AntiBlockManager",
    
    # 子模块
    "ProxyManager",
    "RequestScheduler",
    "BehaviorSimulator",
    "RetryStrategyExecutor",
    
    # 数据模型
    "Proxy",
    "ProxyStatus",
    "ProxyType",
    "RequestConfig",
    "BehaviorConfig",
    
    # 枚举
    "RetryStrategy",
    "RetryDecision",
    "InteractionType",
]

# 默认配置
DEFAULT_REQUEST_CONFIG = RequestConfig(
    min_delay=1.0,
    max_delay=3.0,
    timeout=10,
    max_retries=3,
    retry_backoff_factor=2.0,
    user_agent_rotation=True,
    referer_enabled=True,
)

DEFAULT_BEHAVIOR_CONFIG = BehaviorConfig(
    enable_scroll=True,
    scroll_min_time=3.0,
    scroll_max_time=10.0,
    enable_click=False,
    click_probability=0.3,
    enable_stay=True,
    stay_min_time=2.0,
    stay_max_time=8.0,
)

def create_default_manager(
    enable_proxy: bool = True,
    proxy_api_url: str = None,
    proxy_api_key: str = None,
) -> AntiBlockManager:
    """
    创建默认防封管理器
    
    Args:
        enable_proxy: 是否启用代理池
        proxy_api_url: 代理API地址（如：站大爷）
        proxy_api_key: API密钥
        
    Returns:
        AntiBlockManager实例
    """
    # 1. 创建代理管理器
    proxy_manager = None
    if enable_proxy and proxy_api_url and proxy_api_key:
        proxy_manager = ProxyManager(
            api_url=proxy_api_url,
            api_key=proxy_api_key,
            max_pool_size=100,
        )
    
    # 2. 创建防封管理器
    manager = AntiBlockManager(
        proxy_manager=proxy_manager,
        request_config=DEFAULT_REQUEST_CONFIG,
        behavior_config=DEFAULT_BEHAVIOR_CONFIG,
    )
    
    return manager


def integrate_with_collector(collector_instance, manager: AntiBlockManager):
    """
    将防封管理器集成到采集器中
    
    Args:
        collector_instance: 采集器实例（如 XiaohongshuCollector）
        manager: 防封管理器实例
        
    Usage:
        manager = create_default_manager()
        collector = XiaohongshuCollector()
        integrate_with_collector(collector, manager)
    """
    # 替换采集器的 request 方法
    collector_instance._anti_block_manager = manager
    collector_instance._original_request = collector_instance.request
    
    def _new_request(method, url, **kwargs):
        return manager.request(method, url, **kwargs)
    
    collector_instance.request = _new_request
    
    # 添加便捷方法
    collector_instance.simulate_page_view = lambda page_type="detail": manager.simulate_page_view(page_type)
    collector_instance.switch_proxy = lambda: manager.switch_proxy()
    collector_instance.get_anti_block_stats = lambda: manager.get_stats()
