# Content Pipeline 规格

> 版本: 1.1.0  
> 最后更新: 2026-05-25  
> 状态: 已实现 + 已验证

---

## 1. 核心职责

`ContentPipeline` 是内容处理的主流程编排器，协调采集、过滤、改写、导出等模块。

### 1.1 设计模式

- **外观模式**: 对外提供简化的统一接口
- **异步上下文管理器**: 管理 LLM 连接生命周期
- **策略模式**: 支持多种处理策略组合

---

## 2. 初始化规格

### 2.1 构造函数

```python
class ContentPipeline:
    def __init__(self, config: dict[str, Any]):
        """
        参数：
            config: 配置字典
                - llm: LLM 配置（必需）
                - export: 导出配置（必需）
                - http: HTTP 配置（可选）
                - sources: 数据源配置（可选）
                - translation: 翻译配置（可选）
                - filter: 过滤配置（可选，默认启用）
        """
```

### 2.2 必需配置

```yaml
llm:
  provider: deepseek | openai | qwen
  api_key: 必需
  model: 可选（有默认值）

export:
  output_dir: 必需
```

### 2.3 过滤配置（新增）

```yaml
filter:
  sensitive:
    enabled: true              # 是否启用敏感词过滤
    strict_mode: false        # false=替换, true=拦截
    replace_char: "*"         # 替换字符
    words:
      - "色情"
      - "赌博"
      - "诈骗"
      - "加微信"
      - ...
    
  dedup:
    enabled: true             # 是否启用去重
    exact_dedup: true         # 精确去重（MD5 hash）
    fuzzy_dedup: true         # 模糊去重（相似度）
    similarity_threshold: 0.8 # 相似度阈值
    min_length: 50           # 最小内容长度
```

### 2.4 组件初始化

```python
# 延迟初始化（在 __aenter__ 中）
self.rewrite_processor: RewriteProcessor | None = None

# 立即初始化
self.exporter = Exporter(self.output_dir)

# 过滤器初始化（在 __init__ 中）
self.sensitive_filter = SensitiveFilter(sensitive_config)
self.dedup_filter = DedupFilter(dedup_config)
```

---

## 3. 核心方法

### 3.1 process_url

**功能**: 处理单个 RSS URL

```python
async def process_url(
    self,
    url: str,
    rewrite: bool = True,
    strategy: RewriteStrategy | str | None = None,
    seo: bool = False,
    limit: int | None = None
) -> list[Article]
```

**流程**:
```
1. 创建 RSSCollector（传入 proxy 配置）
2. 调用 collect_async() 采集
3. 限制数量（limit 参数）
4. 遍历每个 Content：
   4a. 敏感词过滤 → 匹配则拦截或替换
   4b. 去重过滤 → 相似则拦截
   4c. 如需改写 → RewriteProcessor.rewrite()
   4d. 如需 SEO → SEOProcessor.optimize()
   4e. 构建 Article 对象
5. 返回 Article 列表
```

**行为约束**:
- 采集失败 → 返回空列表，记录日志
- 改写失败 → 使用原文创建 Article
- SEO 失败 → 跳过 SEO，继续处理

### 3.2 process_all_sources

**功能**: 批量采集配置中的所有源

```python
async def process_all_sources(
    self,
    rewrite: bool = True,
    translate: bool = False,
    target_language: str | None = None,
    seo: bool = False,
    formats: list[str] | None = None,
    limit_per_source: int | None = None
) -> dict[str, Any]
```

**返回结构**:
```python
{
    "articles": [...],         # Article 列表
    "source_results": [...],   # 每个源的采集结果
    "summary": {
        "total_sources": 10,
        "success": 7,
        "skipped": 3,
        "total_articles": 25,
        "elapsed": 45.2
    }
}
```

**支持的数据源**:
```
rss, youtube, twitter, tiktok, douyin, 
xiaohongshu, wechat, sitemap, api
```

**行为约束**:
- 网络错误自动跳过
- 输出友好提示到控制台
- 不中断整体流程

### 3.3 process_source

**功能**: 采集单个指定类型的源

```python
async def process_source(
    self,
    source_type: str,  # 如 "youtube"
    rewrite: bool = True,
    translate: bool = False,
    target_language: str | None = None,
    formats: list[str] | None = None,
    limit_per_source: int | None = None
) -> dict[str, Any]
```

**用途**: 用于独立采集按钮（如 YouTube 采集）

### 3.4 process_contents

**功能**: 处理已有的 Content 列表

### 3.5 _apply_filters（内部方法）

**功能**: 应用过滤器（敏感词 + 去重）

```python
async def _apply_filters(self, content: Content) -> tuple[bool, str]:
    """
    返回: (should_block: bool, reason: str)
    """
```

**流程**:
```
1. 敏感词过滤
   - 如启用 → 调用 SensitiveFilter.process()
   - strict_mode=true → 匹配则拦截
   - strict_mode=false → 替换敏感词，继续处理
   
2. 去重过滤
   - 如启用 → 调用 DedupFilter.process()
   - 相似度 >= 阈值 → 拦截
   - 否则 → 继续处理

返回: (False, "") 或 (True, "敏感词: xxx" 或 "重复内容: xxx")
```

```python
async def process_contents(
    self,
    contents: list[Content],
    rewrite: bool = True
) -> list[Article]
```

**流程**:
```
遍历 contents:
  1. 敏感词过滤 → 匹配则拦截或替换
  2. 去重过滤 → 相似则拦截
  3. 如需改写 → rewrite_processor.rewrite()
  4. 构建 Article（含 metadata）
  5. 异常处理 → fallback 使用原文
返回 Article 列表
```

---

## 4. 配置解析方法

### 4.1 _parse_rss_sources

```python
def _parse_rss_sources(self, source_type: str) -> list[dict]:
    """
    从 config.yaml 的 sources.rss 解析
    过滤 enabled=false 的项
    返回格式: [{"name", "url", "max_items"}, ...]
    """
```

### 4.2 _parse_single_config

```python
def _parse_single_config(self, source_type: str) -> list[dict]:
    """
    解析 youtube/twitter/douyin 等单配置源
    
    支持格式:
    - search_queries: 搜索关键词列表（YouTube）
    - channels/users/accounts: 账号列表
    - sites/endpoints: URL 列表
    
    字段映射:
    - max_items → max_results
    """
```

---

## 5. 导出规格

### 5.1 导出流程

```python
# 自动导出（process_all_sources 中）
if formats:
    for fmt in formats:
        self.exporter.export(article, fmt)

# 手动导出
paths = await pipeline.process_and_export(url, ["markdown", "html"])
```

### 5.2 支持的格式

| 格式 | 标识 | 说明 |
|------|------|------|
| Markdown | `markdown` / `md` | 默认格式 |
| HTML | `html` | 微信公众号风格 |
| JSON | `json` | 结构化数据 |
| 纯文本 | `txt` | 无格式 |
| 小红书 | `xiaohongshu` | XHS 格式 |

---

## 6. 异步上下文管理

### 6.1 生命周期

```python
async with ContentPipeline(config) as pipeline:
    # 进入时：初始化 RewriteProcessor（建立 LLM 连接池）
    # 退出时：关闭 LLM 连接池
    articles = await pipeline.process_url(url)
```

### 6.2 资源管理

```python
async def __aenter__(self):
    self.rewrite_processor = RewriteProcessor(self.config)
    await self.rewrite_processor.__aenter__()
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb):
    if self.rewrite_processor:
        await self.rewrite_processor.__aexit__(exc_type, exc_val, exc_tb)
```

---

## 7. ContentAPI 封装

### 7.1 定位

`ContentAPI` 是对 `ContentPipeline` 的高层封装，提供更简洁的接口。

### 7.2 核心方法

```python
class ContentAPI:
    async def collect_rss(self, url: str) -> list[dict]
    async def rewrite_article(self, article: dict, strategy: str) -> dict
    async def export_article(self, article: dict, formats: list[str]) -> list[str]
    async def process_and_export(self, url: str, formats: list[str]) -> dict
```

### 7.3 使用示例

```python
async with ContentAPI(config) as api:
    # 一键处理
    result = await api.process_and_export(url, ["markdown", "html"])
    
    if result["success"]:
        print(f"导出文件: {result['paths']}")
```

---

## 8. 错误处理规格

### 8.1 采集错误

```python
# 网络错误 → 跳过该源
except Exception as e:
    logger.error(f"采集失败 [{source_name}]: {e}")
    source_results.append({
        "source_name": source_name,
        "success": False,
        "error": str(e)
    })
```

### 8.2 改写错误

```python
# 改写失败 → fallback 使用原文
except Exception as e:
    logger.warning(f"改写失败: {e}")
    article = Article.from_content(content)  # 降级
```

### 8.3 导出错误

```python
# 导出失败 → 记录日志，不中断
except Exception as e:
    logger.error(f"导出失败 ({fmt}): {e}")
```

---

## 9. 日志规格

### 9.1 日志级别

| 级别 | 场景 |
|------|------|
| INFO | 流程关键节点 |
| WARNING | 可恢复的错误 |
| ERROR | 不可恢复错误 |

### 9.2 关键日志点

```python
logger.info(f"Processing URL: {url}")
logger.info(f"Collected: {content.title}")
logger.warning(f"改写失败（{title}）: {error}")
logger.error(f"No content collected from {url}")
```

---

## 10. 性能约束

```
单篇改写超时: 120 秒（LLM 配置）
并发控制: 3 并发（批量改写）
网络超时: 30 秒（HTTP 配置）
重试次数: 3 次（LLM 调用）
```
