"""
内容去重过滤器（支持 TTL 自动过期）
"""

import hashlib
import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timedelta


@dataclass
class DedupFilterConfig:
    """去重配置"""
    enabled: bool = True
    # 相似度阈值（0-1），低于此值视为重复
    similarity_threshold: float = 0.8
    # 使用精确去重（hash）
    exact_dedup: bool = True
    # 使用模糊去重（相似度）
    fuzzy_dedup: bool = True
    # 最小内容长度（低于此值不进行模糊去重）
    min_length: int = 50
    # 去重缓存文件路径（空字符串表示不持久化）
    cache_file: str = ""
    # 去重缓存过期时间（天），0 表示永不过期
    cache_ttl_days: int = 7


class DedupFilter:
    """内容去重过滤器（支持 TTL 自动过期）"""

    def __init__(self, config: DedupFilterConfig):
        self.config = config
        self._seen_hashes: set[str] = set()
        self._seen_contents: list[dict] = []
        # 新增：存储 hash 对应的时间戳 {hash: timestamp}
        self._hash_timestamps: dict[str, float] = {}
        self._pending_saves: int = 0
        self._save_interval: int = 10  # 每积累 10 条保存一次

        # 从缓存文件加载
        self._cache_file = Path(self.config.cache_file) if self.config.cache_file else None
        self._load_cache()

    def _is_expired(self, timestamp: float) -> bool:
        """检查时间戳是否过期（超过 TTL）"""
        if self.config.cache_ttl_days <= 0:
            return False  # TTL=0 表示永不过期
        now = datetime.now().timestamp()
        age_days = (now - timestamp) / 86400  # 86400 秒 = 1 天
        return age_days > self.config.cache_ttl_days

    def _normalize(self, text: str) -> str:
        """标准化文本用于比较"""
        # 去除空白字符，转小写
        text = re.sub(r"\s+", " ", text)
        text = text.lower().strip()
        return text

    def _compute_hash(self, text: str) -> str:
        """计算内容 hash"""
        normalized = self._normalize(text)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _compute_hash_sim(self, text: str, num_bits: int = 64) -> int:
        """计算 SimHash（简化版）"""
        normalized = self._normalize(text)
        # 简单 hash
        h = 0
        for i, char in enumerate(normalized):
            h = ((h << 5) - h + ord(char)) & ((1 << 64) - 1)
        return h

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """计算 Jaccard 相似度"""
        # 分词
        words1 = set(self._normalize(text1).split())
        words2 = set(self._normalize(text2).split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0

    def _levenshtein_similarity(self, text1: str, text2: str) -> float:
        """计算 Levenshtein 相似度（简化版，基于字符重叠）"""
        normalized1 = self._normalize(text1)
        normalized2 = self._normalize(text2)
        
        if not normalized1 or not normalized2:
            return 0.0
        
        # 字符集合相似度
        set1 = set(normalized1)
        set2 = set(normalized2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union else 0.0

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        # 使用多种方法取最大值
        jaccard = self._jaccard_similarity(text1, text2)
        levenshtein = self._levenshtein_similarity(text1, text2)
        
        return max(jaccard, levenshtein)

    async def process(self, content: dict) -> dict[str, Any]:
        """
        检测内容是否重复
        
        Args:
            content: 内容 dict，需包含 title, content 字段
            
        Returns:
            {
                "success": bool,
                "is_duplicate": bool,
                "similar_to": list[str],  # 相似内容的标题
                "similarity_scores": list[float],  # 相似度分数
                "hash": str,  # 内容 hash
                "action": "allow" | "block"
            }
        """
        if not self.config.enabled:
            return {
                "success": True,
                "is_duplicate": False,
                "similar_to": [],
                "similarity_scores": [],
                "hash": "",
                "action": "allow"
            }

        title = content.get("title", "")
        text = content.get("content", "")
        full_text = f"{title}\n{text}"
        
        # 计算 hash
        content_hash = self._compute_hash(full_text)
        is_duplicate = False
        similar_to = []
        similarity_scores = []

        # 1. 精确去重
        if self.config.exact_dedup and content_hash in self._seen_hashes:
            is_duplicate = True

        # 2. 模糊去重
        if not is_duplicate and self.config.fuzzy_dedup:
            if len(full_text) >= self.config.min_length:
                for seen in self._seen_contents:
                    seen_text = f"{seen.get('title', '')}\n{seen.get('content', '')}"
                    similarity = self._compute_similarity(full_text, seen_text)
                    
                    if similarity >= self.config.similarity_threshold:
                        is_duplicate = True
                        similar_to.append(seen.get("title", ""))
                        similarity_scores.append(round(similarity, 3))
                        
                        if len(similar_to) >= 3:  # 最多记录 3 个相似的
                            break

        action = "block" if is_duplicate else "allow"

        # 记录此内容
        if not is_duplicate:
            now = datetime.now().timestamp()
            self._seen_hashes.add(content_hash)
            self._hash_timestamps[content_hash] = now
            self._seen_contents.append({
                "title": title,
                "content": text,
                "hash": content_hash,
                "timestamp": now
            })
            # 保留最近 100 条
            if len(self._seen_contents) > 100:
                self._seen_contents = self._seen_contents[-100:]
            
            # 定期保存缓存（每积累 _save_interval 条保存一次）
            self._pending_saves += 1
            if self._pending_saves >= self._save_interval:
                self._save_cache()

        return {
            "success": True,
            "is_duplicate": is_duplicate,
            "similar_to": similar_to,
            "similarity_scores": similarity_scores,
            "hash": content_hash,
            "action": action
        }

    async def filter_batch(self, contents: list[dict]) -> dict[str, Any]:
        """
        批量去重
        
        Args:
            contents: 内容列表
            
        Returns:
            {
                "success": bool,
                "unique": list[dict],
                "duplicates": list[dict],
                "total": int,
                "unique_count": int,
                "duplicate_count": int
            }
        """
        # 重置状态
        self._seen_hashes.clear()
        self._seen_contents.clear()
        self._hash_timestamps.clear()
        
        unique = []
        duplicates = []
        
        for item in contents:
            result = await self.process(item)
            
            item["dedup_action"] = result.get("action", "unknown")
            item["dedup_hash"] = result.get("hash", "")
            item["dedup_similar_to"] = result.get("similar_to", [])
            
            if result.get("action") == "block":
                duplicates.append(item)
            else:
                unique.append(item)

        return {
            "success": True,
            "unique": unique,
            "duplicates": duplicates,
            "total": len(contents),
            "unique_count": len(unique),
            "duplicate_count": len(duplicates)
        }

    def _load_cache(self) -> None:
        """从缓存文件加载去重数据（自动过滤过期记录）"""
        if not self._cache_file or not self._cache_file.exists():
            return
        try:
            with open(self._cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # 新格式：包含 timestamps（版本 2+）
                if "hash_timestamps" in data:
                    hashes = data.get("hashes", [])
                    timestamps = data.get("hash_timestamps", [])
                    contents = data.get("contents", [])
                    content_timestamps = data.get("content_timestamps", [])
                    
                    # 过滤未过期的 hash
                    valid_count = 0
                    for i, hash_val in enumerate(hashes):
                        ts = timestamps[i] if i < len(timestamps) else 0
                        if not self._is_expired(ts):
                            self._seen_hashes.add(hash_val)
                            self._hash_timestamps[hash_val] = ts
                            valid_count += 1
                    
                    # 过滤未过期的 content
                    for i, content in enumerate(contents):
                        ts = content_timestamps[i] if i < len(content_timestamps) else 0
                        if not self._is_expired(ts):
                            self._seen_contents.append(content)
                    
                    logger.info(f"[Dedup] 加载缓存: {valid_count} 条 hash (已过滤过期), {len(self._seen_contents)} 条内容")
                else:
                    # 旧格式兼容：假设所有记录都有效（未过期）
                    self._seen_hashes = set(data.get("hashes", []))
                    self._seen_contents = data.get("contents", [])
                    # 为旧记录补充当前时间戳
                    now = datetime.now().timestamp()
                    for hash_val in self._seen_hashes:
                        self._hash_timestamps[hash_val] = now
                    logger.info(f"[Dedup] 加载缓存（旧格式）: {len(self._seen_hashes)} 条 hash, {len(self._seen_contents)} 条内容")
        except Exception as e:
            logger.warning(f"[Dedup] 加载缓存失败: {e}")

    def _save_cache(self) -> None:
        """保存去重数据到缓存文件（内部方法，包含时间戳）"""
        if not self._cache_file:
            return
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 构建带时间戳的数据
            hashes = list(self._seen_hashes)
            timestamps = [self._hash_timestamps.get(h, 0) for h in hashes]
            
            # 只保存最近 100 条 content
            contents = self._seen_contents[-100:]
            now = datetime.now().timestamp()
            content_timestamps = [now] * len(contents)  # 简化：所有 content 使用当前时间
            
            data = {
                "hashes": hashes,
                "hash_timestamps": timestamps,
                "contents": contents,
                "content_timestamps": content_timestamps,
                "count": len(hashes),
                "version": 2  # 版本 2：包含时间戳
            }
            with open(self._cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"[Dedup] 保存缓存: {len(hashes)} 条 hash (含时间戳)")
            self._pending_saves = 0
        except Exception as e:
            logger.warning(f"[Dedup] 保存缓存失败: {e}")

    def save_cache(self) -> None:
        """强制保存缓存（供外部调用）"""
        self._save_cache()

    def reset(self) -> None:
        """重置去重状态（清除内存+文件缓存）"""
        self._seen_hashes.clear()
        self._seen_contents.clear()
        self._hash_timestamps.clear()
        self._pending_saves = 0
        
        # 删除缓存文件
        if self._cache_file and self._cache_file.exists():
            try:
                self._cache_file.unlink()
                logger.info(f"[Dedup] 缓存文件已删除: {self._cache_file}")
            except Exception as e:
                logger.warning(f"[Dedup] 删除缓存文件失败: {e}")
        
        logger.info("[Dedup] 去重缓存已重置")

    def shutdown(self) -> None:
        """关闭时保存缓存"""
        self._save_cache()
