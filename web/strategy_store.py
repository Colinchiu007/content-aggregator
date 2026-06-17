"""
改写策略存储模块

使用 JSON 文件持久化改写策略（自定义策略）。
内置策略（深度改写等 6 种）在代码中硬编码，不存储。
"""

import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class StrategyStore:
    """改写策略存储器（JSON 文件持久化）"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.cache_file = data_dir / "strategies_cache.json"
        self.strategies: List[Dict] = []
        self._load()

    def _load(self):
        """从 JSON 文件加载策略"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    self.strategies = json.load(f)
        except Exception:
            self.strategies = []

    def save(self):
        """持久化到 JSON 文件"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.strategies, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存策略缓存失败: {e}")

    def get_all(self) -> List[Dict]:
        """获取所有自定义策略"""
        return self.strategies.copy()

    def get_by_id(self, strategy_id: str) -> Optional[Dict]:
        """按 ID 获取策略"""
        for s in self.strategies:
            if s.get("id") == strategy_id:
                return s
        return None

    def create(self, name: str, description: str, is_default: bool = False) -> Dict:
        """创建新策略"""
        # 如果设为默认，先将其他策略设为非默认
        if is_default:
            self._clear_default()

        strategy_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        strategy = {
            "id": strategy_id,
            "name": name,
            "description": description,
            "is_default": 1 if is_default else 0,
            "created_at": now,
            "updated_at": now,
        }
        self.strategies.append(strategy)
        self.save()
        return strategy

    def update(self, strategy_id: str, name: str = None, description: str = None, is_default: bool = None) -> Optional[Dict]:
        """更新策略"""
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            return None

        if name is not None:
            strategy["name"] = name
        if description is not None:
            strategy["description"] = description
        if is_default is not None:
            if is_default:
                self._clear_default()
            strategy["is_default"] = 1 if is_default else 0

        strategy["updated_at"] = datetime.now().isoformat()
        self.save()
        return strategy

    def delete(self, strategy_id: str) -> bool:
        """删除策略。如果删除的是默认策略，提示用户先设置新默认"""
        strategy = self.get_by_id(strategy_id)
        if not strategy:
            return False

        # 如果删除默认策略，需要有其他默认策略替代（由调用方检查）
        self.strategies = [s for s in self.strategies if s.get("id") != strategy_id]
        self.save()
        return True

    def get_default(self) -> Optional[Dict]:
        """获取当前默认策略"""
        for s in self.strategies:
            if s.get("is_default") == 1:
                return s
        return None

    def _clear_default(self):
        """清除所有策略的默认标记"""
        for s in self.strategies:
            s["is_default"] = 0

    def count(self) -> int:
        """策略总数"""
        return len(self.strategies)
