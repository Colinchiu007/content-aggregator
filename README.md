# Content Aggregator

**内容聚合与改写平台** — 将互联网优质内容转化为标准化内容资产，支持多源采集、AI 深度改写、多格式导出，赋能内容创作者高效运营多平台。

---

## 核心特性

### 📡 多源内容采集
- **RSS 订阅源**：支持代理，自动解析 Feed 内容
- **自定义 URL 采集**：指定任意网页链接进行采集
- **多源聚合**：配置多个 RSS 源，支持按关键词过滤

### ✍️ AI 智能改写（6 种策略）
内置六种改写策略，支持通过 `config.yaml` 自定义提示词模板：

| 策略 | 说明 |
|------|------|
| `SUMMARIZE` | 摘要提取，200–500 字核心要点 |
| `STYLE_TRANSFER` | 风格迁移，转换为指定文案风格 |
| `PARAPHRASE` | 伪原创，同义替换保持语义一致 |
| `REWRITE` | 深度改写，重新组织结构与表达 |
| `EXPAND` | 内容扩展，补充背景/案例/数据 |
| `SHORT_VIDEO` | 短视频文案仿写，保持 40–50% 相似度 |

支持 DeepSeek / OpenAI / Qwen 等主流 LLM API，可通过配置文件灵活切换。

### 🔍 内容过滤与质量控制
- **敏感词过滤**：DFA 算法，支持自定义词库和白名单
- **内容去重**：SimHash + MinHash 相似度检测，防止重复发布

### 📤 多格式导出
| 格式 | 说明 | 适用场景 |
|------|------|----------|
| Markdown | 标准结构化文档 | 通用存档、二次编辑 |
| HTML | 微信内联样式 | 公众号直接粘贴发布 |
| JSON | 完整结构化数据 | Skill 间调用、程序处理 |
| TXT | 纯文本 | 配音、摘要、纯内容 |
| 小红书 | emoji + 标签格式 | 小红书平台发布 |

### 💻 CLI 命令行工具
```bash
# 单条 RSS 处理
python scripts/run.py --url "https://example.com/rss.xml" --format markdown

# 批量处理（从文件读取 URL）
python scripts/run.py --file urls.txt --format markdown --format html

# 指定改写策略
python scripts/run.py --url "..." --strategy SHORT_VIDEO

# 跳过 AI 改写（仅采集）
python scripts/run.py --url "..." --no-rewrite --format html
```

---

## Web UI（可选）

项目内置 Web 管理界面，支持可视化操作：

### 启动 Web UI
```bash
# 方式一：直接启动（开发）
python -m uvicorn web.server:app --host 127.0.0.1 --port 8000 --reload

# 方式二：通过脚本启动
python scripts/web.py
```

浏览器访问：`http://127.0.0.1:8000`

### 功能页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 文章列表 | `/articles` | 查看/搜索/删除已采集文章 |
| 文章详情 | `/articles/{id}` | 查看文章完整内容 |
| 内容改写 | `/compose` | 手动输入内容并 AI 改写 |
| 数据源管理 | `/sources` | 管理 RSS/YouTube 等数据源 |
| 定时任务 | `/scheduler` | 创建/编辑/启停定时采集任务 |
| 任务管理 | `/tasks` | 查看异步任务进度和历史 |
| 系统设置 | `/settings` | 修改 LLM 配置等参数 |

### Web API（异步任务模式）

所有耗时操作（采集/改写）均为**异步任务**，提交后返回 `task_id`，前端轮询获取结果：

```bash
# 1. 提交采集任务
curl -X POST "http://127.0.0.1:8000/api/collect/url" \

  -d "url=https://sspai.com/feed&source_type=rss&rewrite=true"
# 返回: {"task_id": "task_xxx", "status": "started"}

# 2. 轮询任务状态
curl "http://127.0.0.1:8000/api/tasks/task_xxx"
# 返回: {"status": "done", "progress": 100, ...}
```

> 📖 完整 API 文档见 `docs/API.md`

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置
```bash
cp config/config.example.yaml config/config.yaml
# 编辑 config.yaml，填入 LLM API Key
```

**最小配置示例（`config.yaml`）：**
```yaml
llm:
  provider: "deepseek"
  api_key: "${LLM_API_KEY}"   # 或直接填入 "sk-xxx"
  model: "deepseek-chat"
  base_url: "https://api.deepseek.com"

export:
  output_dir: "./output/exports"
```

### 3. 运行
```bash
# CLI 模式（单次采集）
python scripts/run.py --url "https://feeds.feedburner.com/ruanyifeng" --format markdown

# Web UI 模式（可视化操作）
python -m uvicorn web.server:app --host 127.0.0.1 --port 8000
# 然后访问 http://127.0.0.1:8000
```

---

## Python 模块调用

```python
import asyncio
from content_aggregator import ContentPipeline

config = {
    "llm": {
        "provider": "deepseek",
        "api_key": "sk-xxx",
        "model": "deepseek-chat",
    },
    "export": {
        "output_dir": "./output/exports"
    }
}

async def main():
    async with ContentPipeline(config) as pipeline:
        article = await pipeline.process_url("https://example.com/rss.xml")
        path = pipeline.exporter.export(article, "markdown")
        print(f"导出至: {path}")

asyncio.run(main())
```

### 高级：自定义提示词
```python
from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy

# 方式一：代码级自定义（最高优先级）
config = RewriteConfig(
    strategy=RewriteStrategy.SHORT_VIDEO,
    custom_prompt="你的自定义提示词内容..."
)

# 方式二：配置文件覆盖（config.yaml）
# rewrite:
#   prompts:
#     short_video: |
#       你的自定义短视频改写提示词...
```

---

## 项目结构

```
content-aggregator/
├── config/
│   ├── config.yaml          # 运行配置
│   └── config.example.yaml  # 配置示例
├── src/content_aggregator/
│   ├── sources/              # 数据采集
│   │   └── rss.py           # RSS 采集器（含代理支持）
│   ├── processors/           # 内容处理
│   │   ├── rewrite.py       # AI 改写（6 种策略）
│   │   ├── formatter.py     # 内容格式化
│   │   └── filter/          # 内容过滤
│   │       ├── sensitive.py # 敏感词过滤
│   │       └── dedup.py     # 相似度去重
│   ├── exporters/           # 多格式导出
│   ├── storage/             # 数据持久化（SQLite）
│   ├── workflows/           # 处理流水线
│   └── models.py            # 数据模型
├── scripts/                 # CLI 脚本与测试
├── output/exports/          # 导出文件目录
├── SPEC.md                  # 详细功能规格说明
├── CHANGELOG.md             # 变更记录
└── requirements.txt
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12+ |
| HTTP | httpx（异步，代理支持）|
| RSS 解析 | feedparser |
| LLM | OpenAI 兼容 API |
| 配置 | Pydantic v2 |
| 数据库 | SQLite + aiosqlite |
| 日志 | Loguru |

---

## License

MIT
