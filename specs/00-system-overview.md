# Content Aggregator 系统规格

> 版本: 1.0.0  
> 最后更新: 2026-05-25  
> 状态: 反向工程自现有代码

---

## 1. 系统定位

**Content Aggregator** 是一个内容聚合与改写平台，将互联网热文转化为标准化内容资产，供多平台发布使用。

### 1.1 核心价值

| 输入 | 输出 |
|------|------|
| RSS、YouTube、Twitter 等多源内容 | 统一格式的内容资产 |
| 原创文章 | AI 改写后的伪原创内容 |
| 多语言内容 | 中文内容（可选翻译） |

### 1.2 技术栈

- **后端**: Python 3.12 + FastAPI
- **前端**: Jinja2 模板 + 原生 CSS/JS
- **LLM**: DeepSeek / OpenAI / Qwen（可配置）
- **数据库**: SQLite（默认）

---

## 2. 核心流程

```
采集 → 过滤 → 改写 → 翻译（可选） → SEO（可选） → 格式化 → 导出
```

### 2.1 处理步骤说明

| 步骤 | 说明 | 可选 |
|------|------|------|
| 采集 | 从数据源获取原始内容 | ❌ |
| 过滤 | 敏感词检测 + simhash 去重 | ❌ |
| 改写 | AI 改写内容 | ✅ |
| 翻译 | 先翻译成中文再改写 | ✅ |
| SEO | 提取关键词、生成摘要 | ✅ |
| 格式化 | 转为 Markdown/HTML/JSON | ✅ |
| 导出 | 保存到文件系统 | ✅ |

---

## 3. 数据模型

### 3.1 Content（原始内容）

```python
@dataclass
class Content:
    id: str                    # UUID
    source_id: str             # 数据源标识
    source_type: str           # rss/youtube/twitter...
    url: str                   # 原文链接
    title: str                 # 标题
    content: str               # 正文
    summary: str               # 摘要
    author: str                # 作者
    published_at: datetime     # 发布时间
    metadata: dict             # 扩展元数据
    raw_data: Any              # 原始数据
```

### 3.2 Article（处理后文章）

```python
@dataclass
class Article:
    id: str                    # UUID
    title: str                 # 改写后标题
    original_title: str        # 原始标题
    source: str                # 来源名称
    source_url: str            # 原文链接
    author: str                # 作者
    published_at: datetime      # 发布时间
    content: str               # 改写后正文
    summary: str                # 摘要
    tags: list[str]            # 标签列表
    word_count: int            # 字数
    metadata: dict             # 元数据（含改写信息）
```

---

## 4. 数据源支持

### 4.1 已支持的数据源

| 源类型 | 标识 | 认证方式 | 采集限制 |
|--------|------|----------|----------|
| RSS | `rss` | 无 | N/A |
| YouTube | `youtube` | API Key | 10000 单位/天 |
| Twitter/X | `twitter` | Bearer Token | API v2 |
| TikTok | `tiktok` | Session Cookie | N/A |
| 抖音 | `douyin` | Cookie + Client Key | N/A |
| 小红书 | `xiaohongshu` | Cookie + Token | N/A |
| 微信公众号 | `wechat` | 第三方 API Key | 依赖服务商 |
| Sitemap | `sitemap` | 无 | N/A |
| 自定义 API | `api` | 自定义 | N/A |

### 4.2 数据源行为规格

#### RSS 源
```
输入: RSS Feed URL
输出: Content 列表
限制:
  - 单次最多 100 篇
  - 超时 30 秒自动跳过
  - 支持 HTTP 代理
```

#### YouTube 源
```
输入: channel_id / playlist_id / search_query
输出: Content 列表（含字幕）
限制:
  - 需要 YouTube Data API v3 Key
  - 免费额度每天 10000 单位
  - 搜索消耗 100 单位/次
```

---

## 5. 改写策略

### 5.1 支持的策略

| 策略 | 标识 | 说明 | 输出特点 |
|------|------|------|----------|
| 摘要提取 | `summarize` | 提取核心观点 | 200-500 字 |
| 风格迁移 | `style_transfer` | 改变写作风格 | 保持原文长度 |
| 伪原创 | `paraphrase` | 调整表达方式 | 同义替换 |
| 深度改写 | `rewrite` | 重新组织结构 | 500-5000 字 |
| 内容扩展 | `expand` | 添加背景案例 | 扩展至 3000+ 字 |
| 短视频文案 | `short_video` | 仿写短视频脚本 | 口语化表达 |

### 5.2 改写行为约束

```
字数要求:
  - 最小字数: 500 字
  - 最大字数: 5000 字
  - 目标字数: 3000 字（可配置）

提示词优先级:
  1. RewriteConfig.custom_prompt（最高）
  2. config.yaml -> rewrite.prompts[strategy]
  3. 内置默认 SYSTEM_PROMPTS

输出约束:
  - 禁止寒暄前缀（如"好的，这是为您改写的文章"）
  - 必须直接输出改写结果
  - 支持先翻译再改写（translate_to="zh"）
```

---

## 6. Web UI 规格

### 6.1 页面清单

| 路径 | 页面名称 | 功能 |
|------|----------|------|
| `/` | 仪表盘 | 统计概览 + 快捷操作 |
| `/articles` | 文章列表 | 查看/搜索/删除文章 |
| `/sources` | 数据源 | 采集入口 |
| `/settings` | 数据源配置 | 编辑 config.yaml |
| `/compose` | 手动输入 | 粘贴内容直接改写 |
| `/tasks` | 任务列表 | 异步任务状态 |
| `/scheduler` | 定时调度 | Cron 任务管理 |

### 6.2 UI 行为约束

```
主题: 深色主题（Dark Theme）
响应式: 支持移动端（隐藏侧边栏）
交互:
  - 异步操作显示 spinner
  - 操作结果使用 Toast 通知
  - 表格支持分页（每页 20 条）
```

---

## 7. API 规格

### 7.1 核心端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/collect` | POST | 采集指定源 |
| `/api/rewrite` | POST | 改写指定内容 |
| `/api/export` | POST | 导出文章 |
| `/api/articles` | GET | 获取文章列表 |
| `/api/articles/{id}` | DELETE | 删除文章 |
| `/api/tasks` | GET | 获取任务列表 |

### 7.2 错误处理

```json
{
  "success": false,
  "error": "错误类型",
  "message": "详细信息"
}
```

---

## 8. 配置规格

### 8.1 必需配置

```yaml
llm:
  provider: deepseek | openai | qwen
  api_key: 必需
  model: 可选（有默认值）

export:
  output_dir: 必需
```

### 8.2 可选配置

```yaml
http:
  timeout: 30
  proxy: null
  proxy_fallback: skip

translation:
  enabled: false
  default_language: EN

scheduler:
  enabled: false
```

---

## 9. 约束与边界

### 9.1 功能边界

| 支持 | 不支持 |
|------|--------|
| 多源采集 | 实时推送 |
| AI 改写 | 图片改写 |
| 多格式导出 | PDF 直接编辑 |
| 定时调度 | 分布式部署 |

### 9.2 性能约束

```
单篇改写: ≤ 120 秒
批量采集: 每源 ≤ 100 篇
并发限制: 默认 3 并发
存储限制: SQLite 单文件 ≤ 1GB
```

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-05-25 | 初始规格，反向工程自 v0.1.0 代码 |
