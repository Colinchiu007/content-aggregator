---
name: content-aggregator-design
description: content-aggregator DESIGN.md — 设计细节
---

# Content Aggregator — 设计文档

> **版本**: v1.8.0 | **更新**: 2026-07-01

## 一、采集器设计

### 1.1 BaseCollector 接口

```python
class BaseCollector(ABC):
    async def fetch(self, config: SourceConfig) -> list[Content]: ...
    async def test(self) -> bool: ...
```

### 1.2 9 类采集器

| 采集器 | 认证方式 | 速率限制 |
|--------|---------|---------|
| RSSCollector | 无 | — |
| YouTubeCollector | API Key | 10K units/day |
| TwitterCollector | Bearer Token | 500K tweets/month |
| TikTokCollector | Session Cookie | 按 IP |
| DouyinCollector | Cookie + Client Key | 按 IP |
| XiaohongshuCollector | Cookie + Token | 按 IP |
| WechatCollector | 第三方 API | 按 API |
| SitemapCollector | 无 | — |
| APICollector | 自定义 Header | 自定义 |

## 二、改写策略设计

| 策略 | 输出长度 | LLM 温度 | System Prompt |
|------|---------|---------|-------------|
| summarize | 200-500 | 0.3 | 摘要提取 |
| style_transfer | 同原文 | 0.5 | 风格迁移 |
| paraphrase | 同原文 | 0.6 | 同义改写 |
| rewrite | 500-5000 | 0.7 | 深度改写 |
| expand | 3000+ | 0.8 | 内容扩展 |
| short_video | 口语化 | 0.7 | 短视频文案 |

三级提示词优先级：`custom_prompt` > `config.yaml prompts` > 内置默认值。

## 三、过滤设计

### SensitiveFilter
- 算法：DFA（确定性有限自动机）
- 模式：strict 拦截 / 非 strict 替换
- 自定义词库 + 白名单 + 拼音检测

### DedupFilter
- 精确去重：MD5 URL hash
- 模糊去重：SimHash + MinHash（阈值 0.8）

## 四、导出格式

| 格式 | 类名 | 特点 |
|------|------|------|
| Markdown | MarkdownExporter | YAML frontmatter |
| HTML | HTMLExporter | 微信内联样式 |
| JSON | JSONExporter | 完整结构化字段 |
| TXT | TXTExporter | 纯文本 |
| PDF | PDFExporter | reportlab |
| Excel | ExcelDataStore | 样式化表格 |

## 五、测试

62/62 测试 ALL GREEN：API 端点 / 采集器 / 改写 / 过滤 / 导出 / 发布集成。
