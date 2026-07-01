"""
防封采集 - 行为模拟器
模拟真人浏览行为：停留、滑动、点击
"""
import random
import time
from typing import Optional, List, Dict, Any
from enum import Enum


class InteractionType(str, Enum):
    """互动类型"""
    LIKE = "like"
    COMMENT = "comment"
    SHARE = "share"
    FOLLOW = "follow"


class BehaviorSimulator:
    """行为模拟器"""

    def __init__(
        self,
        enable_stay: bool = True,
        stay_min_time: float = 2.0,
        stay_max_time: float = 8.0,
        enable_scroll: bool = True,
        scroll_min_time: float = 3.0,
        scroll_max_time: float = 10.0,
        enable_click: bool = False,
        click_probability: float = 0.3,
        enable_interaction: bool = False,
        interaction_probability: float = 0.1,
    ):
        """
        Args:
            enable_stay: 是否启用停留模拟
            stay_min_time: 最小停留时间（秒）
            stay_max_time: 最大停留时间（秒）
            enable_scroll: 是否启用滑动模拟
            scroll_min_time: 最小滑动时间（秒）
            scroll_max_time: 最大滑动时间（秒）
            enable_click: 是否启用点击模拟
            click_probability: 点击概率（0~1）
            enable_interaction: 是否启用互动模拟（点赞/评论/分享）
            interaction_probability: 互动概率（0~1）
        """
        self.enable_stay = enable_stay
        self.stay_min_time = stay_min_time
        self.stay_max_time = stay_max_time
        self.enable_scroll = enable_scroll
        self.scroll_min_time = scroll_min_time
        self.scroll_max_time = scroll_max_time
        self.enable_click = enable_click
        self.click_probability = click_probability
        self.enable_interaction = enable_interaction
        self.interaction_probability = interaction_probability

    def simulate_stay(self) -> float:
        """模拟停留"""
        if not self.enable_stay:
            return 0.0
        
        stay_time = random.uniform(self.stay_min_time, self.stay_max_time)
        time.sleep(stay_time)
        return stay_time

    def simulate_scroll(self) -> float:
        """模拟滑动"""
        if not self.enable_scroll:
            return 0.0
        
        scroll_time = random.uniform(self.scroll_min_time, self.scroll_max_time)
        # 模拟多次短滑动
        intervals = random.randint(3, 8)
        for _ in range(intervals):
            chunk = scroll_time / intervals
            time.sleep(chunk + random.uniform(-0.5, 0.5))  # 加点随机性
        return scroll_time

    def simulate_click(self) -> bool:
        """模拟点击"""
        if not self.enable_click:
            return False
        
        if random.random() < self.click_probability:
            # 模拟点击后的短暂停留
            time.sleep(random.uniform(0.5, 2.0))
            return True
        return False

    def simulate_interaction(self) -> Optional[InteractionType]:
        """模拟互动（点赞/评论/分享）"""
        if not self.enable_interaction:
            return None
        
        if random.random() < self.interaction_probability:
            interaction = random.choice(list(InteractionType))
            # 模拟互动后的停留
            time.sleep(random.uniform(1.0, 3.0))
            return interaction
        return None

    def simulate_page_view(self, page_type: str = "detail") -> Dict[str, Any]:
        """
        模拟页面浏览（综合行为）
        
        Args:
            page_type: 页面类型（search/list/detail）
        """
        result = {
            "page_type": page_type,
            "stay_time": 0.0,
            "scroll_time": 0.0,
            "clicked": False,
            "interaction": None,
        }

        # 1. 页面加载后停留
        result["stay_time"] = self.simulate_stay()

        # 2. 滑动浏览
        result["scroll_time"] = self.simulate_scroll()

        # 3. 偶尔点击
        result["clicked"] = self.simulate_click()

        # 4. 偶尔互动
        interaction = self.simulate_interaction()
        if interaction:
            result["interaction"] = interaction.value

        return result

    def get_behavior_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """
        获取行为相关的请求头（模拟浏览器）
        
        Args:
            referer: 来源页面
        """
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none" if not referer else "same-origin",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        if referer:
            headers["Referer"] = referer

        return headers
