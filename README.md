# Content Aggregator

内容聚合与改写平台 - 将互联网热文转化为标准化内容资产

## 功能

- 📡 **多源采集**：RSS、自定义URL
- ✍️ **AI改写**：DeepSeek/OpenAI/Qwen 支持
- 📤 **多格式导出**：Markdown、HTML、JSON、TXT、小红书格式
- 🔧 **Skill封装**：Python模块化设计，供其他Skill调用

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置

编辑 `config/config.yaml`，填入 LLM API Key：

```yaml
llm:
  api_key: "sk-your-api-key"
  provider: "deepseek"  # deepseek / openai / qwen
  model: "deepseek-chat"
```

### 使用

#### 命令行

```bash
# 处理 RSS 并导出 Markdown
python scripts/run.py --url "https://example.com/rss.xml" --format markdown

# 不使用 AI 改写（仅采集）
python scripts/run.py --url "https://example.com/rss.xml" --no-rewrite --format html
```

#### Python 模块

```python
import asyncio
from content_aggregator import ContentPipeline

config = {
    "llm": {
        "provider": "deepseek",
        "api_key": "sk-xxx",
        "model": "deepseek-chat"
    },
    "export": {
        "output_dir": "./output/exports"
    }
}

async def main():
    async with ContentPipeline(config) as pipeline:
        # 处理单个URL
        article = await pipeline.process_url("https://example.com/rss.xml")
        
        # 导出
        path = pipeline.exporter.export(article, "markdown")
        print(f"Exported to: {path}")

asyncio.run(main())
```

## 项目结构

```
content-aggregator/
├── config/
│   └── config.yaml       # 配置文件
├── src/content_aggregator/
│   ├── sources/          # 数据源（RSS等）
│   ├── processors/       # 处理器（改写、格式化）
│   ├── exporters/        # 导出器（多种格式）
│   ├── workflows/        # 工作流（流水线）
│   └── api/              # API接口
├── output/exports/       # 导出目录
├── tests/                # 测试
├── scripts/              # 脚本
├── SPEC.md               # 详细规格说明
└── requirements.txt      # 依赖
```

## 导出格式

| 格式 | 说明 | 用途 |
|------|------|------|
| Markdown | 标准Markdown | 通用文档 |
| HTML | 微信内联样式 | 公众号直接用 |
| JSON | 结构化数据 | Skill间调用 |
| TXT | 纯文本 | 配音/摘要 |
| 小红书 | 带emoji标签 | 小红书平台 |

## License

MIT