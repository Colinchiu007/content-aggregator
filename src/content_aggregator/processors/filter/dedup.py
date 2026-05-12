"""
内容去重过滤器
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


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


class DedupFilter:
    """内容去重过滤器"""

    def __init__(self, config: DedupFilterConfig):
        self.config = config
        self._seen_hashes: set[str] = set()
        self._seen_contents: list[dict] = []

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
            self._seen_hashes.add(content_hash)
            self._seen_contents.append({
                "title": title,
                "content": text,
                "hash": content_hash
            })
            # 保留最近 100 条
            if len(self._seen_contents) > 100:
                self._seen_contents = self._seen_contents[-100:]

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

    def reset(self) -> None:
        """重置去重状态"""
        self._seen_hashes.clear()
        self._seen_contents.clear()