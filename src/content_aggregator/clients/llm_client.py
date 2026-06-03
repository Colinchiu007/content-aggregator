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
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


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
    """

    def __init__(self, config: dict[str, Any]):
        """
        初始化 LLM 客户端
        
        Args:
            config: LLM 配置字典，包含：
                - provider: 提供商名称 (deepseek/openai/qwen/custom)
                - api_key: API 密钥
                - model: 模型名称
                - base_url: API 基础 URL (可选)
                - max_tokens: 最大 token 数 (默认 4096)
                - temperature: 温度参数 (默认 0.7)
                - retry: 重试次数 (默认 3)
                - timeout: 超时时间秒 (默认 120)
        """
        self.provider = config.get("provider", "deepseek").lower()
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "deepseek-chat")
        self.base_url = config.get("base_url", "")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)
        self.retry = config.get("retry", 3)
        self.timeout = config.get("timeout", 120)
        
        # HTTP 客户端（延迟初始化）
        self._client: httpx.AsyncClient | None = None
        
        # 日志
        logger.info(f"[LLMClient] Initialized: provider={self.provider}, model={self.model}")

    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（延迟初始化）"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
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
                    content = result["choices"][0]["message"]["content"]
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
"""
如何添加新的 LLM provider 支持：

1. 在 LLMClient 类中添加新的 `_call_xxx()` 方法：
    ```python
    async def _call_ernie(self, prompt: str) -> dict:
        # 1. 获取 access_token（百度 ERNIE 需要）
        token_url = "https://aip.baidu.com/oauth/2.0/token"
        token_response = await self.client.post(token_url, ...)
        access_token = token_response.json()["access_token"]
        
        # 2. 调用 ERNIE API
        url = f"https://aip.baidu.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self.model}?access_token={access_token}"
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }
        response = await self.client.post(url, json=payload)
        result = response.json()
        
        # 3. 返回统一格式
        return {
            "content": result["result"],
            "usage": {...}
        }
    ``

2. 在 `call()` 方法中添加路由：
    ```python
    async def call(self, prompt: str) -> dict:
        if self.provider in ["deepseek", "openai", "qwen"]:
            return await self._call_openai_compatible(prompt)
        elif self.provider == "ernie":
            return await self._call_ernie(prompt)  # 新增
        ...
    ``

3. 更新配置文件示例（`config.yaml`）：
    ```yaml
    llm:
      provider: "ernie"  # 新增 provider
      model: "ernie-4.0-turbo-8k"
      api_key: "your-client-id"
      api_secret: "your-client-secret"  # ERNIE 需要 secret
      base_url: "https://aip.baidu.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"
    ```

4. 如果 provider 需要额外参数（如 ERNIE 的 `api_secret`），在 `__init__()` 中添加：
    ```python
    self.api_secret = config.get("api_secret", "")
    ```

# ============================
# 测试代码
# ============================
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # 测试配置
        config = {
            "provider": "deepseek",
            "api_key": "sk-test-key",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "max_tokens": 1024,
            "temperature": 0.7,
        }
        
        client = LLMClient(config)
        
        try:
            result = await client.call("用一句话介绍 Python")
            print("Content:", result["content"])
            print("Usage:", result["usage"])
        finally:
            await client.close()
    
    asyncio.run(test())
