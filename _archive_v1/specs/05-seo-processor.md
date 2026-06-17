# SEO Processor 规格

> 版本: 1.0.0  
> 最后更新: 2026-05-27  
> 状态: 基于现有代码反向工程

---

## 1. 概述

### 1.1 功能定位

SEO Processor 通过 **LLM 智能提取** SEO 元素（而非传统 TF-IDF 规则），一次性生成：
- **关键词**（keywords）
- **Meta 描述**（meta_description）
- **Meta 标题**（meta_title，可选）
- **优化标签**（optimized_tags）

### 1.2 设计决策

| 决策 | 理由 |
|------|------|
| 用 LLM 而非规则 | 中文语境理解更好，可捕捉语义相关词 |
| 一次性调用生成所有元素 | 减少 token 开销（1 次调用 vs 4 次） |
| 返回结构化结果，不直接修改 Article | 由调用方决定如何使用（灵活） |
| 要求 LLM 输出严格 JSON | 便于解析，容错处理 |

---

## 2. 数据模型

### 2.1 SEOConfig

```python
@dataclass
class SEOConfig:
    """SEO 优化配置"""
    max_keywords: int = 8          # 最大关键词数量
    description_length: int = 160   # Meta 描述最大长度（字符）
    max_tags: int = 5              # 最大标签数量
    language: str = "zh-CN"        # 内容语言
```

**默认值说明**:
- `max_keywords=8`: 避免过多关键词分散权重
- `description_length=160`: Google 搜索结果页最多显示 ~160 字符
- `max_tags=5`: 标签过多显得不专注
- `language="zh-CN"`: 默认中文，影响分词和关键词提取策略

### 2.2 SEOResult

```python
@dataclass
class SEOResult:
    """SEO 优化结果"""
    success: bool                  # 是否成功
    keywords: list[str]           # 提取的关键词列表
    meta_description: str = ""    # 生成的 Meta Description
    meta_title: str = ""         # 优化的 Meta Title（可选）
    optimized_tags: list[str]     # 优化后的标签
    error: str | None = None     # 错误信息
    duration: float = 0.0        # 处理耗时（秒）
```

**字段说明**:
- `keywords`: 按重要性排序，`len(keywords) <= max_keywords`
- `meta_description`: 不超过 `description_length` 字符，自然语言（非关键词堆砌）
- `meta_title`: 若原标题已优化，可返回空字符串（表示无需修改）
- `optimized_tags`: 基于内容重新生成（可能和原 tags 不同）

---

## 3. 处理器实现

### 3.1 SEOProcessor 类

```python
class SEOProcessor:
    """
    SEO 优化处理器
    
    通过 LLM 一次性生成关键词、描述和标签。
    """
    
    SYSTEM_PROMPT = """..."""  # 见 3.2 节
    
    def __init__(self, config: dict[str, Any]):
        """初始化"""
        self.config = config
        self.llm_config = config.get("llm", {})
        self.client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "SEOProcessor":
        """进入异步上下文，创建 HTTP 客户端"""
        timeout = self.llm_config.get("timeout", 60)
        proxy = self.llm_config.get("proxy") or self.config.get("proxy")
        self.client = httpx.AsyncClient(timeout=timeout, proxy=proxy)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出异步上下文，关闭 HTTP 客户端"""
        if self.client:
            await self.client.aclose()
    
    async def optimize(
        self,
        content: Content,
        seo_config: SEOConfig | None = None,
    ) -> SEOResult:
        """对内容执行 SEO 优化（主入口）"""
        # 1. 使用默认配置（如未提供）
        # 2. 构造 system prompt（替换占位符）
        # 3. 截取正文前 3000 字（足够 SEO 分析）
        # 4. 调用 LLM
        # 5. 解析 JSON 响应
        # 6. 返回 SEOResult
    
    async def _call_llm(self, system: str, user: str) -> str | None:
        """调用 LLM API"""
        # 1. 根据 provider 选择 base_url（deepseek/openai/qwen）
        # 2. POST /v1/chat/completions
        # 3. 返回 data["choices"][0]["message"]["content"]
    
    @staticmethod
    def _parse_response(text: str) -> dict:
        """解析 LLM 返回的 JSON（容错）"""
        # 1. 尝试提取 ```json ... ``` 代码块
        # 2. 尝试直接 json.loads
        # 3. 尝试 raw_decode（提取第一个 { } 块）
        # 4. 全部失败返回 {}
```

### 3.2 System Prompt

```
You are an SEO expert. Given an article title and content, generate SEO metadata in STRICT JSON format:

{
  "keywords": ["keyword1", "keyword2", ...],
  "meta_description": "A compelling description under {max_desc} characters for search engines",
  "meta_title": "An optimized title (optional, can be same as original if already good)",
  "tags": ["tag1", "tag2", ...]
}

Rules:
- keywords: Extract the most important keywords/phrases that users would search for. Max {max_kw} items.
- meta_description: Write a compelling, click-worthy description. Include primary keywords naturally. Under {max_desc} characters.
- meta_title: Keep or slightly improve the original title for better CTR. Under 60 characters.
- tags: Category-like tags for content organization. Max {max_tags} items.
- Language: Match the article's language ({lang}).
- Output ONLY valid JSON, no markdown, no explanation.
```

**占位符替换**:
- `{max_kw}` → `seo_config.max_keywords`
- `{max_desc}` → `seo_config.description_length`
- `{max_tags}` → `seo_config.max_tags`
- `{lang}` → `seo_config.language`

### 3.3 调用参数

```python
{
    "model": "deepseek-chat",      # 可配置
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    "temperature": 0.3,           # 低温度，保持准确性
    "max_tokens": 500,             # SEO 响应较短，500 足够
}
```

**为什么 temperature=0.3？**
- SEO 需要准确性（关键词提取不能太随机）
- 描述需要吸引力（不能完全 deterministic）

---

## 4. 使用流程

### 4.1 基本用法

```python
from content_aggregator.processors.seo import SEOProcessor, SEOConfig, SEOResult
from content_aggregator.models import Content

# 1. 准备内容
content = Content(
    id="uuid",
    title="AI 大模型技术综述",
    content="正文内容...",
)

# 2. 创建处理器（使用异步上下文管理器）
async with SEOProcessor(CONFIG) as seo:
    result: SEOResult = await seo.optimize(content)
    
    # 3. 处理结果
    if result.success:
        print(result.keywords)          # ['AI', '大模型', '深度学习', ...]
        print(result.meta_description)    # "本文综述 AI 大模型技术..."
        print(result.meta_title)         # "AI 大模型技术综述（可选优化）"
        print(result.optimized_tags)     # ['AI', '技术', '深度学习', ...]
    else:
        print(f"SEO 优化失败: {result.error}")
```

### 4.2 自定义配置

```python
config = SEOConfig(
    max_keywords=10,              # 提取最多 10 个关键词
    description_length=200,        # Meta 描述最长 200 字符
    max_tags=8,                   # 最多 8 个标签
    language="en-US",             # 英文文章
)

async with SEOProcessor(CONFIG) as seo:
    result = await seo.optimize(content, config)
```

### 4.3 集成到 Pipeline

```python
# workflows/pipeline.py（伪代码）
class ContentPipeline:
    async def process_contents(self, contents: list[Content], ...) -> list[Article]:
        articles = []
        
        for content in contents:
            # 1. 改写
            rewritten = await self._rewrite(content)
            
            # 2. SEO 优化（可选，由配置控制）
            if self.config.get("seo", {}).get("enabled", False):
                async with SEOProcessor(self.config) as seo:
                    seo_result = await seo.optimize(rewritten)
                    if seo_result.success:
                        content.metadata["seo_keywords"] = seo_result.keywords
                        content.metadata["seo_description"] = seo_result.meta_description
                        content.metadata["seo_title"] = seo_result.meta_title
                        content.tags = seo_result.optimized_tags  # 覆盖原标签
            
            # 3. 翻译（可选）
            # ...
            
            # 4. 导出
            articles.append(Article.from_content(content))
        
        return articles
```

---

## 5. LLM 调用规格

### 5.1 支持的 Provider

| Provider | base_url | 默认模型 |
|----------|----------|----------|
| `deepseek` | `https://api.deepseek.com` | `deepseek-chat` |
| `openai` | `https://api.openai.com` | `gpt-3.5-turbo` |
| `qwen` | `https://dashscope.aliyuncs.com/compatible-mode` | `qwen-turbo` |

**配置方式**:
```yaml
# config.yaml
llm:
  provider: "deepseek"
  api_key: "sk-xxx"
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"  # 可选，自动根据 provider 选择
  timeout: 60
  proxy: "http://127.0.0.1:7890"     # 可选
```

### 5.2 请求格式

```python
POST {base_url}/v1/chat/completions

Headers:
    Authorization: Bearer {api_key}
    Content-Type: application/json

Body:
{
    "model": "deepseek-chat",
    "messages": [
        {
            "role": "system",
            "content": "You are an SEO expert..."
        },
        {
            "role": "user",
            "content": "Title: AI 大模型技术综述\n\nContent:\n正文内容..."
        }
    ],
    "temperature": 0.3,
    "max_tokens": 500
}
```

### 5.3 响应解析

**期望响应格式**:
```json
{
  "choices": [
    {
      "message": {
        "content": "{\n  \"keywords\": [\"AI\", \"大模型\", ...],\n  \"meta_description\": \"...\",\n  \"meta_title\": \"...\",\n  \"tags\": [...]\n}"
      }
    }
  ]
}
```

**容错处理**（`_parse_response` 方法）:
1. **提取代码块**: 正则匹配 ```json ... ```
2. **直接解析**: `json.loads(text)`
3. **raw_decode**: `json.JSONDecoder().raw_decode(text)` 提取第一个 `{ }` 块
4. **全部失败**: 记录警告，返回 `{}`

---

## 6. 输出示例

### 6.1 输入

```python
content = Content(
    title="AI 大模型技术综述",
    content="人工智能大模型（Large Language Model, LLM）是...（3000 字）",
)
```

### 6.2 LLM 输出（期望）

```json
{
  "keywords": ["AI", "大模型", "深度学习", "自然语言处理", "GPT", "Transformer"],
  "meta_description": "本文综述人工智能大模型（LLM）的核心技术、应用场景和发展趋势，帮助读者快速了解 AI 大模型的全貌。",
  "meta_title": "AI 大模型技术综述：核心技术与发展趋势",
  "tags": ["AI", "人工智能", "大模型", "技术综述", "深度学习"]
}
```

### 6.3 解析后 SEOResult

```python
SEOResult(
    success=True,
    keywords=['AI', '大模型', '深度学习', '自然语言处理', 'GPT', 'Transformer'],
    meta_description='本文综述人工智能大模型（LLM）的核心技术、应用场景和发展趋势...',
    meta_title='AI 大模型技术综述：核心技术与发展趋势',
    optimized_tags=['AI', '人工智能', '大模型', '技术综述', '深度学习'],
    error=None,
    duration=2.5
)
```

---

## 7. 错误处理

### 7.1 常见错误

| 错误类型 | 原因 | 处理方式 |
|----------|------|----------|
| `LLM returned empty response` | API 超时或返回空 | 返回 `success=False, error="LLM returned empty response"` |
| `LLM API error: 429` | 请求频率限制 | 建议用户增加 `retry` 配置 |
| `JSONDecodeError` | LLM 输出非合法 JSON | 容错解析（见 5.3 节），失败返回空结果 |
| `EnvironmentError` | `api_key` 未配置 | 抛出例外，由调用方处理 |

### 7.2 错误返回

```python
# 所有错误均返回 SEOResult(success=False, error=...)
# 不抛出异常（优雅降级）

result = await seo.optimize(content)
if not result.success:
    logger.warning(f"SEO optimization failed: {result.error}")
    # 继续使用原始内容（无 SEO 优化）
```

---

## 8. 配置示例

### 8.1 config.yaml

```yaml
# config.yaml
llm:
  provider: "deepseek"
  api_key: "sk-xxx"
  model: "deepseek-chat"
  timeout: 60
  retry: 3

# SEO 配置（可选）
seo:
  enabled: true
  max_keywords: 8
  description_length: 160
  max_tags: 5
  language: "zh-CN"

# 代理配置（可选）
proxy: "http://127.0.0.1:7890"
```

### 8.2 禁用 SEO

```yaml
# config.yaml
seo:
  enabled: false  # Pipeline 跳过 SEO 优化
```

---

## 9. 测试清单

- [ ] 正常流程：LLM 返回合法 JSON → 解析成功
- [ ] LLM 返回非 JSON → 容错解析成功
- [ ] LLM 返回空响应 → `success=False`
- [ ] API 429 错误 → 返回错误，不崩溃
- [ ] 中文内容 → 提取中文关键词
- [ ] 英文内容 → 提取英文关键词
- [ ] `max_keywords=3` → 返回 ≤ 3 个关键词
- [ ] `description_length=100` → 描述 ≤ 100 字符
- [ ] 异步上下文管理器正确关闭客户端

---

## 10. 下一步行动

1. **补充单元测试** - 测试各种 LLM 响应格式（合法 JSON、非 JSON、空响应）
2. **添加重试机制** - SEO 调用失败时重试（类似 RewriteProcessor）
3. **支持批量优化** - 一次调用优化多篇文章（减少 API 调用次数）
4. **添加 SEO 评分** - 基于关键词密度、描述质量等给出评分

---

## 11. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-27 | 初始版本，基于 `processors/seo.py` 反向工程 |
