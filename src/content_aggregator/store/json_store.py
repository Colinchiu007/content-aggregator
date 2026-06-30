"""
JSON 数据存储 — 按平台/日期分目录存储

目录结构:
    output/collected/
    └── <source_name>/
        └── <YYYY-MM-DD>.json    # 每条包含完整采集元数据
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from content_aggregator.sources.collectors.base_collector import SourceResult
from .abstract import DataStore


class JsonDataStore(DataStore):
    """JSON 文件存储"""

    def __init__(self, base_dir: str = "./output/collected"):
        self.base_dir = Path(base_dir)

    def _ensure_dir(self, source_name: str) -> Path:
        """确保平台目录存在"""
        d = self.base_dir / source_name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _date_path(self, source_name: str) -> Path:
        """当日文件的路径"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self._ensure_dir(source_name) / f"{date_str}.json"

    async def save(self, result: SourceResult) -> str:
        filepath = self._date_path(result.source_name)
        entry = {
            "source_name": result.source_name,
            "collected_at": datetime.now().isoformat(),
            "success": result.success,
            "error": result.error,
            "collected_count": result.collected_count,
            "skipped_count": result.skipped_count,
            "duration": result.duration,
            "metadata": result.metadata,
            "articles": result.data,
        }

        records = []
        if filepath.exists():
            records = json.loads(filepath.read_text(encoding="utf-8"))

        records.append(entry)

        filepath.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(filepath)

    async def query(self, source_name: Optional[str] = None,
                    limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        source_dirs = [self.base_dir / source_name] if source_name else self.base_dir.iterdir()

        for d in source_dirs:
            if not d.is_dir():
                continue
            for fpath in sorted(d.glob("*.json"), reverse=True):
                records = json.loads(fpath.read_text(encoding="utf-8"))
                for rec in records:
                    for article in rec.get("articles", []):
                        article["_source"] = rec["source_name"]
                        article["_collected_at"] = rec["collected_at"]
                        results.append(article)

        results.sort(key=lambda x: x.get("_collected_at", ""), reverse=True)
        return results[offset:offset + limit]

    async def count(self, source_name: Optional[str] = None) -> int:
        total = 0
        source_dirs = [self.base_dir / source_name] if source_name else self.base_dir.iterdir()
        for d in source_dirs:
            if not d.is_dir():
                continue
            for fpath in d.glob("*.json"):
                records = json.loads(fpath.read_text(encoding="utf-8"))
                total += len(records)
        return total
