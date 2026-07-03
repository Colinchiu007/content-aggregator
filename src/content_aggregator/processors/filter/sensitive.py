"""
敏感词过滤器
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SensitiveFilterConfig:
    """敏感词过滤配置"""
    enabled: bool = True
    # 敏感词列表（默认中文敏感词示例）
    words: list[str] = field(default_factory=lambda: [
        # 政治敏感
        "色情", "赌博", "毒品", "暴力", "恐怖",
        # 诈骗相关
        "诈骗", "传销", "非法集资",
        # 违规广告
        "加微信", "扫码", "免费领", "点击就送",
    ])
    # 替换字符
    replace_char: str = "*"
    # 是否严格模式（匹配即过滤）
    strict_mode: bool = False


class SensitiveFilter:
    """敏感词过滤器"""

    def __init__(self, config: SensitiveFilterConfig):
        self.config = config

    def process(self, content_text: str) -> dict[str, Any]:
        """
        检测并处理敏感词
        
        Args:
            content_text: 待检测文本
            
        Returns:
            {
                "success": bool,
                "has_sensitive": bool,
                "matched_words": list[str],  # 匹配的敏感词
                "filtered_text": str,        # 处理后的文本
                "action": "allow" | "block"  # 处理动作
            }
        """
        if not self.config.enabled:
            return {
                "success": True,
                "has_sensitive": False,
                "matched_words": [],
                "filtered_text": content_text,
                "action": "allow"
            }

        matched_words = []
        filtered_text = content_text
        
        for word in self.config.words:
            # 不区分大小写匹配
            pattern = re.escape(word)
            if re.search(pattern, content_text, re.IGNORECASE):
                matched_words.append(word)
                
                # 替换为星号
                if self.config.replace_char:
                    filtered_text = re.sub(
                        pattern, 
                        self.config.replace_char * len(word),
                        filtered_text,
                        flags=re.IGNORECASE
                    )

        has_sensitive = len(matched_words) > 0
        
        # 根据模式决定动作
        action = "block" if (has_sensitive and self.config.strict_mode) else "allow"

        return {
            "success": True,
            "has_sensitive": has_sensitive,
            "matched_words": matched_words,
            "filtered_text": filtered_text if not self.config.strict_mode else content_text,
            "action": action
        }

    def filter_batch(self, contents: list[dict]) -> dict[str, Any]:
        """
        批量过滤内容
        
        Args:
            contents: 内容列表（dict 格式，需包含 title, content 字段）
            
        Returns:
            {
                "success": bool,
                "passed": list[dict],   # 通过的内容
                "blocked": list[dict],  # 拦截的内容
                "total": int,
                "passed_count": int,
                "blocked_count": int
            }
        """
        passed = []
        blocked = []
        
        for item in contents:
            title = item.get("title", "")
            content = item.get("content", "")
            full_text = f"{title}\n{content}"
            
            # 检测标题
            title_result = self.process(title)
            # 检测内容
            content_result = self.process(content)
            
            # 合并匹配的词
            all_matched = list(set(
                title_result.get("matched_words", []) + 
                content_result.get("matched_words", [])
            ))
            
            # 更新内容
            item["filtered_content"] = content_result.get("filtered_text", content)
            item["matched_sensitive_words"] = all_matched
            
            if title_result.get("action") == "block" or content_result.get("action") == "block":
                item["filter_action"] = "blocked"
                blocked.append(item)
            else:
                item["filter_action"] = "passed"
                passed.append(item)

        return {
            "success": True,
            "passed": passed,
            "blocked": blocked,
            "total": len(contents),
            "passed_count": len(passed),
            "blocked_count": len(blocked)
        }

    def add_sensitive_words(self, words: list[str]) -> None:
        """添加敏感词"""
        for word in words:
            if word not in self.config.words:
                self.config.words.append(word)

    def remove_sensitive_words(self, words: list[str]) -> None:
        """移除敏感词"""
        for word in words:
            if word in self.config.words:
                self.config.words.remove(word)