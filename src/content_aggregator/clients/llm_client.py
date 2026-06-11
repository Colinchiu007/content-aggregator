"""
统一 LLM 客户端
支持多种 LLM 提供商，提供统一的调用接口

扩展方法：
1. 在 `LLMClient` 类中添加新的 `_call_xxx()` 方法
2. 在 `call()` 方法的路由逻辑中添加新 provider
3. 更新配置文件支持新 provider

示例：添加 ERNIE
    async def _call_ernie(self, prompt: str) -> dict:
        # ERNIE 特定逻辑
        pass

    # 在 call() 中添加：
    elif provider == "ernie":
        return await self._call_ernie(prompt)
"""
import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _is_reasoning_content(content: str) -> bool:
    """判断文本是否是推理/分析内容（而非正式文章）"""
    if not content:
        return True

    c = content.strip()

    # 1. 以英文标点/小写字母开头 → 推理内容
    if c and (c[0].isascii() and not c[0].isascii() == False):  # 简化：首字符是ASCII
        # 更精确：首字符是英文标点或字母
        if c[0] in '.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
            return True

    # 2. 检测英文推理特征（句子开头模式）
    english_reasoning_starts = [
        '. The ', '. I ', '. First', '. Let',
        'The first', 'I need', 'Let me', 'First,', 'Actually,',
        'Looking at', 'Based on', 'In this', 'To ', 'Alright',
        'Okay,', 'So,', 'Hmm,', 'Well,', 'Now,',
        'The user', 'The content', 'The article',
    ]
    for pat in english_reasoning_starts:
        if c.startswith(pat) or c[:100].find(pat) != -1:
            return True

    # 3. 中文字符比例过低（< 15%）→ 可能是英文推理
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', c))
    total_chars = len(c)
    if total_chars > 30 and chinese_chars / total_chars < 0.15:
        return True

    # 4. 包含 <think> 标签
    if "<think>" in c or "</think>" in c:
        return True

    return False


def _extract_final_from_reasoning(reasoning: str) -> str:
    """
    从推理内容中提取最终答案
    
    Args:
        reasoning: 推理内容
        
    Returns:
        提取的最终答案，如果无法提取则返回空字符串
    """
    if not reasoning:
        return ""
    
    # 策略 1：查找 <think> 标签后的内容
    _think_pat = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    matches = _think_pat.findall(reasoning)
    if matches:
        # 返回最后一个 <think> 块之后的内容
        last_think_end = reasoning.rfind("</think>")
        if last_think_end != -1:
            final = reasoning[last_think_end + len("</think>"):].strip()
            if final:
                return final
    
    # 策略 2：查找答案标记
    answer_markers = ["答案：", "回答：", "最终答案：", "Answer:", "Final answer:"]
    for marker in answer_markers:
        idx = reasoning.rfind(marker)
        if idx != -1:
            return reasoning[idx + len(marker):].strip()
    
    # 策略 3：返回最后一段作为答案
    paragraphs = reasoning.split("\n\n")
    if paragraphs:
        return paragraphs[-1].strip()
    
    return ""


class LLMClient:
    """
    统一 LLM 客户端
    
    使用示例：
        config = {
            "provider": "deepseek",
            "api_key": "sk-xxx",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "max_tokens": 4096,
            "temperature": 0.7,
            "retry": 3,
        }
        client = LLMClient(config)
        result = await client.call("写一篇文章关于...")
        print(result["content"])
    
    config 支持两种格式：
    1. 旧版扁平格式：{"provider": ..., "api_key": ..., "model": ..., "base_url": ...}
    2. 新版多模型格式：{"models": [...], "default_model_id": "..."}（自动提取默认模型）
    """

    @staticmethod
    def _normalize_config(config: dict) -> dict:
        """将新旧两种配置格式统一为扁平格式"""
        if "models" in config and isinstance(config["models"], list):
            # 新版多模型格式 - 提取默认模型
            models = config["models"]
            default_id = config.get("default_model_id", "")
            # 找默认模型
            model_cfg = next(
                (m for m in models if m.get("id") == default_id or m.get("is_default")),
                models[0] if models else None
            )
            if model_cfg:
                return {
                    "provider": config.get("provider", "openai"),
                    "api_key": model_cfg.get("api_key", ""),
                    "model": model_cfg.get("model_id", ""),
                    "base_url": model_cfg.get("base_url", ""),
                    "max_tokens": config.get("max_tokens", 4096),
                    "temperature": config.get("temperature", 0.7),
                    "retry": config.get("retry", 3),
                    "timeout": config.get("timeout", 120),
                }
        # 旧版扁平格式或空配置 - 原样返回
        return config

    @staticmethod
    def _decrypt_key(key: str | None) -> str | None:
        """解密 enc: 前缀的加密 Key（与 YouTubeCollector 相同逻辑）"""
        if not key or not key.startswith('enc:'):
            return key
        
        try:
            from cryptography.fernet import Fernet
            import os
            
            # 获取加密密钥
            enc_key = os.environ.get('CONTENT_AGGREGATOR_ENC_KEY')
            if not enc_key:
                # 从 config.yaml 读取 encryption_key
                import pathlib, yaml
                config_path = pathlib.Path(__file__).parent.parent.parent / "config" / "config.yaml"
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        cfg = yaml.safe_load(f)
                        enc_key = cfg.get('encryption_key')
                except Exception:
                    pass
            
            if not enc_key:
                logger.warning('[LLMClient] 未找到加密密钥，无法解密 API Key')
                return None
            
            # 解密
            fernet = Fernet(enc_key.encode())
            decrypted = fernet.decrypt(key[4:].encode())  # 去掉 'enc:' 前缀
            return decrypted.decode('utf-8')
            
        except Exception as e:
            logger.error(f'[LLMClient] API Key 解密失败: {e}')
            return None

    def __init__(self, config: dict[str, Any]):
        """
        初始化 LLM 客户端
        
        Args:
            config: LLM 配置字典。支持新旧两种格式（自动标准化）
        """
        # 标准化配置（兼容新旧两种格式）
        config = self._normalize_config(config)
        
        # 解密 API Key（如果是 enc: 前缀）
        self.provider = config.get("provider", "deepseek").lower()
        raw_key = config.get("api_key", "")
        self.api_key = self._decrypt_key(raw_key) or ""
        self.model = config.get("model", "deepseek-chat")
        self.base_url = config.get("base_url", "")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)
        self.retry = config.get("retry", 3)
        self.timeout = config.get("timeout", 120)
        self.http_proxy = config.get("http_proxy", "") or ""
        
        # HTTP 客户端（延迟初始化）
        self._client: httpx.AsyncClient | None = None
        
        # 日志
        logger.info(f"[LLMClient] Initialized: provider={self.provider}, model={self.model}")

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（延迟初始化）"""
        if self._client is None:
            # 有代理则用代理，无代理则直连（trust_env=False 避免环境变量干扰）
            kwargs = {"timeout": self.timeout, "trust_env": False}
            if self.http_proxy:
                kwargs["proxy"] = self.http_proxy
                logger.info(f"[LLMClient] Using configured proxy: {self.http_proxy}")
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def call(self, prompt: str) -> dict:
        """
        统一调用接口
        
        Args:
            prompt: 用户输入的提示词
            
        Returns:
            dict: {
                "content": str,  # LLM 生成的文本内容
                "usage": dict,     # token 使用统计
            }
            
        Raises:
            ValueError: 配置错误（缺少 api_key、model 等）
            Exception: API 调用失败（重试后仍然失败）
        """
        if not self.api_key:
            raise ValueError("LLM API key is required")
        
        if not self.model:
            raise ValueError("LLM model is required")
        
        # 路由到对应的 provider 实现
        if self.provider in ["deepseek", "openai", "qwen", "moonshot", "minimax"]:
            # OpenAI 兼容接口（大多数国内 LLM 都支持）
            return await self._call_openai_compatible(prompt)
        
        elif self.provider == "custom":
            # 自定义 provider（用户自己实现）
            return await self._call_custom(prompt)
        
        else:
            # 未知 provider，尝试作为 OpenAI 兼容接口调用
            logger.warning(f"[LLMClient] Unknown provider '{self.provider}', trying OpenAI-compatible format")
            return await self._call_openai_compatible(prompt)

    async def _call_openai_compatible(self, prompt: str) -> dict:
        """
        调用 OpenAI 兼容接口（DeepSeek、Qwen、OpenAI、Moonshot 等）
        
        这些提供商都使用相同的 /chat/completions 端点格式
        """
        # 构造 URL
        if self.base_url:
            # 用户指定了 base_url
            url = f"{self.base_url}/chat/completions"
        else:
            # 使用默认 URL
            defaults = {
                "openai": "https://api.openai.com",
                "deepseek": "https://api.deepseek.com",
                "qwen": "https://dashscope.aliyuncs.com/api/v1",
                "moonshot": "https://api.moonshot.cn/v1",
                "minimax": "https://api.minimax.chat/v1",
            }
            base = defaults.get(self.provider, "https://api.openai.com")
            url = f"{base}/chat/completions"
        
        # 构造请求
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        logger.info(f"[_call_openai_compatible] START: provider={self.provider}, model={self.model}, url={url}")
        logger.info(f"[_call_openai_compatible] Prompt length: {len(prompt)} chars")
        
        # 重试逻辑
        last_error = None
        for attempt in range(self.retry):
            try:
                logger.info(f"[_call_openai_compatible] Attempt {attempt + 1}/{self.retry}")
                
                response = await self.client.post(url, json=data, headers=headers)
                
                if response.status_code == 200:
                    result = response.json()
                    message = result["choices"][0]["message"]
                    # 兼容不同模型返回格式：
                    # - 普通模型：message.content
                    # - 推理模型（如 sensenova-6.7-flash-lite）：message.reasoning 或 message.reasoning_content
                    # ⚠️ 优先使用 content；只有 content 为 None 时才 fallback 到 reasoning
                    content = message.get("content")
                    reasoning = message.get("reasoning") or message.get("reasoning_content", "")
                    # 推理模型响应处理：content + reasoning 字段
                    raw_content = message.get("content") or ""
                    reasoning = message.get("reasoning") or message.get("reasoning_content") or ""

                    # 清理 raw_content 中的 <think> 等推理标签
                    if raw_content:
                        _think_pat = re.compile(r"<think>.*?</think>", re.DOTALL)
                        raw_content = _think_pat.sub("", raw_content).strip()

                    # 决定最终使用的 content
                    content = raw_content

                    if not content or _is_reasoning_content(content):
                        # raw_content 为空或是推理内容，尝试从 reasoning 字段提取
                        content = _extract_final_from_reasoning(reasoning)
                        if not content:
                            # reasoning 也无法提取，使用 raw_content
                            content = raw_content

                    # 最终保险：去掉开头非中文字符的英文推理前缀
                    if content:
                        # 找到第一个中文字符的位置
                        _fc = re.search(r'[\u4e00-\u9fff]', content)
                        if _fc and _fc.start() > 0:
                            _prefix = content[:_fc.start()].strip()
                            # 如果前缀看起来像英文推理（含英文单词），则去掉
                            if re.search(r'[a-zA-Z]{5,}', _prefix):
                                logger.warning(f"[_call_openai_compatible] 去掉英文推理前缀（{_fc.start()} chars），前缀: {_prefix[:100]}")
                                content = content[_fc.start():].strip()

                    # 最终保险2：如果 content 仍为空且有 reasoning，截取 reasoning 后半部分
                    if not content and reasoning:
                        mid = len(reasoning) // 2
                        content = reasoning[mid:].strip()
                        logger.warning(f"[_call_openai_compatible] 无法提取最终答案，使用 reasoning 后半段，前200字: {content[:200]}")
                    usage = result.get("usage", {})
                    
                    logger.info(f"[_call_openai_compatible] SUCCESS: got {len(content)} chars, usage={usage}")
                    
                    return {
                        "content": content,
                        "usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                            "total_tokens": usage.get("total_tokens", 0),
                        }
                    }
                
                elif response.status_code == 429:
                    # 速率限制
                    wait_time = 2 ** attempt
                    logger.warning(f"[_call_openai_compatible] Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                else:
                    error_msg = f"API error: {response.status_code} - {response.text}"
                    logger.error(f"[_call_openai_compatible] ERROR: {error_msg}")
                    raise Exception(error_msg)
            
            except Exception as e:
                last_error = e
                logger.warning(f"[_call_openai_compatible] Attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(1)
        
        logger.error(f"[_call_openai_compatible] FAILED after {self.retry} attempts: {last_error}")
        raise Exception(f"LLM call failed after {self.retry} attempts: {last_error}")

    async def _call_custom(self, prompt: str) -> dict:
        """
        自定义 provider 调用接口
        
        用户可以在配置中指定：
            - custom_url: 自定义端点 URL
            - custom_headers: 自定义请求头
            - custom_body: 自定义请求体模板
        
        未来可以扩展为：
            - 从配置文件加载自定义 provider 实现
            - 动态加载 Python 模块
        """
        # TODO: 实现自定义 provider 逻辑
        # 示例：从配置读取自定义端点和格式
        raise NotImplementedError("Custom provider not yet implemented")

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "LLMClient":
        """
        从配置字典创建 LLMClient
        
        Args:
            config: 配置字典，格式：
                {
                    "llm": {
                        "provider": "deepseek",
                        "api_key": "sk-xxx",
                        ...
                    }
                }
                
        Returns:
            LLMClient 实例
        """
        llm_config = config.get("llm", {})
        return cls(llm_config)


# ============================
# 扩展指南
# ============================
# 如何添加新的 LLM provider 支持：
# 
# 1. 在 LLMClient 类中添加新的 `_call_xxx()` 方法：
#     ```python
#     async def _call_ernie(self, prompt: str) -> dict:
#         # 1. 获取 access_token（百度 ERNIE 需要）
#         token_url = "https://aip.baidu.com/oauth/2.0/token"
#         token_response = await self.client.post(token_url, ...)
#         access_token = token_response.json()["access_token"]
#         
#         # 2. 调用 ERNIE API
#         url = f"https://aip.baidu.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self.model}?access_token={access_token}"
#         payload = {
#             "messages": [{"role": "user", "content": prompt}],
#             "temperature": self.temperature,
#         }
#         response = await self.client.post(url, json=payload)
#         result = response.json()
#         
#         # 3. 返回统一格式
#         return {
#             "content": result["result"],
#             "usage": {...}
#         }
#     ``
# 
# 2. 在 `call()` 方法中添加路由：
#     ```python
#     async def call(self, prompt: str) -> dict:
#         if self.provider in ["deepseek", "openai", "qwen"]:
#             return await self._call_openai_compatible(prompt)
#         elif self.provider == "ernie":
#             return await self._call_ernie(prompt)  # 新增
#         ...
#     ``
# 
# 3. 更新配置文件示例（`config.yaml`）：
#     ```yaml
#     llm:
#       provider: "ernie"  # 新增 provider
#       model: "ernie-4.0-turbo-8k"
#       api_key: "your-client-id"
#       api_secret: "your-client-secret"  # ERNIE 需要 secret
#       base_url: "https://aip.baidu.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"
#     ```
# 
# 4. 如果 provider 需要额外参数（如 ERNIE 的 `api_secret`），在 `__init__()` 中添加：
#     ```python
#     self.api_secret = config.get("api_secret", "")
#     ```

# ============================
# 测试代码
# ============================
# if __name__ == "__main__":
#     import asyncio
#     
#     async def test():
#         # 测试配置
#         config = {
#             "provider": "deepseek",
#             "api_key": "sk-test-key",
#             "model": "deepseek-chat",
#             "base_url": "https://api.deepseek.com",
#             "max_tokens": 1024,
#             "temperature": 0.7,
#         }
#         
#         client = LLMClient(config)
#         
#         try:
#             result = await client.call("用一句话介绍 Python")
#             print("Content:", result["content"])
#             print("Usage:", result["usage"])
#         finally:
#             await client.close()
#     
#     asyncio.run(test())
