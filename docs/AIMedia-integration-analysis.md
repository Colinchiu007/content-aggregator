# AIMedia 项目架构分析与 PROJECT-001 整合方案

> 分析日期：2026-06-03  
> 参考项目：[Anning01/AIMedia](https://github.com/Anning01/AIMedia) + [Anning01/article-spider](https://github.com/Anning01/article-spider)  
> 目标项目：PROJECT-001 (content-aggregator)

---

## 一、AIMedia 项目架构总览

### 1.1 项目定位
AIMedia 是一个**工程级重量级**全自动媒体内容生产系统，包含：
- **Django 5.x 后端**（RESTful API + 数据库 + 任务调度）
- **PySide6 桌面客户端**（GUI）
- **完整生态**：支付、登录、多平台发布

### 1.2 核心模块

```
AIMedia/
├── back/                          # Django 后端
│   ├── apps/crawlers/             # 爬虫模块
│   │   ├── crawler_data/          # 爬虫数据模型
│   │   ├── crawler_service.py     # 爬虫服务层
│   │   └── api_urls.py            # 爬虫 API 路由
│   ├── apps/users/                # 用户模块
│   ├── apps/article/              # 文章管理
│   ├── apps/publish/              # 多平台发布
│   └── ...
├── pyside/                        # PySide6 桌面端
│   ├── ui/                        # UI 界面
│   └── utils/                     # 工具函数
```

### 1.3 支持的热点源

| 来源 | AIMedia 实现 | article-spider 实现 |
|------|------------|-------------------|
| 抖音热点 | ✅ Django crawler | ❌ 无 |
| 网易新闻 | ✅ Django crawler | ✅ wangyi.py |
| 微博热点 | ✅ Django crawler | ❌ 无 |
| 澎湃新闻 | ✅ Django crawler | ✅ pengpai.py |
| 搜狐新闻 | ✅ Django crawler | ✅ souhu.py |
| 中国日报 | ✅ Django crawler | ✅ zhongguoribao.py |
| 新浪新闻 | ❌ | ✅ xinlang.py |
| IT之家 | ❌ | ✅ ithome.py |
| 腾讯新闻 | ❌ | ✅ tengxunxinwen.py |

---

## 二、article-spider（轻量爬虫库）架构分析

这是 AIMedia 作者专门拆分出来的**纯爬虫子项目**，架构非常轻量，**最适合整合**。

### 2.1 技术栈
| 组件 | 技术 |
|------|------|
| 异步框架 | asyncio |
| HTTP 客户端 | aiohttp |
| HTML 解析 | lxml (XPath) |
| 数据库 | PostgreSQL + asyncpg |
| 环境配置 | python-dotenv |

### 2.2 核心设计模式

```
base.py (BaseSpider 基类)
  ├── request(url)          # 异步 HTTP，自动处理编码
  ├── get_news_list(html)   # 解析列表页 → 文章链接列表 (子类实现)
  ├── get_news_info(html, url)  # 解析详情页 → 文章信息 (子类实现)
  ├── save_article(article) # 保存文章到数据库
  └── crawl_and_save(limit) # 执行抓取流程

main.py (入口)
  └── spiders = {           # 注册所有爬虫
        'wangyi': {'spider': WangYiSpider, 'url': ..., 'interval': 180},
        ...
  }
```

### 2.3 每个爬虫文件结构（以 wangyi.py 为例）
```python
class WangYiSpider(BaseSpider):
    source_name = "网易新闻"
    category = "新闻"
    
    async def get_news_list(self, html: str) -> list:
        # 用 lxml XPath 解析列表页，返回文章链接
    
    async def get_news_info(self, html: str, url: str) -> dict | None:
        # 用 lxml XPath 解析详情页，返回 {title, content, publish_time, author}
```

**特点**：
- ✅ 极简：每个爬虫 ~100 行代码
- ✅ 统一接口：所有爬虫继承同一个基类
- ✅ 可配置间隔：每个源独立设置抓取频率
- ✅ 自动建表：首次运行自动创建数据库表

---

## 三、PROJECT-001 现状分析

### 3.1 已有能力
| 模块 | 状态 |
|------|------|
| RSS 采集 | ✅ 成熟，支持代理 |
| YouTube 采集 | ✅ 已实现 |
| 抖音采集 | ✅ 已实现（douyin_collector.py），但仅支持用户主页视频，**不支持热点榜** |
| 微博采集 | ❌ 未实现 |
| 网易新闻 | ❌ 未实现 |
| AI 改写 | ✅ 6 种策略成熟 |
| 敏感词过滤 | ✅ DFA 算法 |
| 内容去重 | ✅ SimHash + MinHash |
| 多格式导出 | ✅ Markdown/HTML/JSON/TXT/小红书 |
| Web UI | ✅ FastAPI + 前端 |
| 定时任务 | ✅ 内置 scheduler |

### 3.2 架构差异对比

| 维度 | PROJECT-001 | AIMedia article-spider |
|------|-----------|---------------------|
| HTTP 库 | httpx (异步) | aiohttp |
| HTML 解析 | BeautifulSoup | lxml (XPath) |
| 数据库 | SQLite (aiosqlite) | PostgreSQL (asyncpg) |
| 爬虫模式 | 按 Source 类组织 | 按 Spider 文件组织 |
| 配置方式 | config.yaml + Pydantic | .env 环境变量 |
| 架构重量 | 中等（FastAPI + Web UI） | 极轻（纯爬虫） |

---

## 四、整合方案：轻量化整合策略

### ⚠️ 核心原则
**不要直接搬 AIMedia 的 Django 后端和 PySide6 桌面端**——太重了。  
只整合 article-spider 的**爬虫逻辑**，适配到 PROJECT-001 的现有架构。

### 4.1 需要新增的采集器

#### 目标 1：抖音热点榜（非用户视频）
**现状**：PROJECT-001 的 `douyin_collector.py` 只能采集**指定用户的视频列表**，无法采集抖音热榜。

**整合思路**：
- 参考 AIMedia 的抖音热点爬虫逻辑
- 抖音热榜接口：`https://www.douyin.com/aweme/v1/web/hot/search/list/`
- 需要 Cookie 或免登录（热榜是公开数据）
- 新增文件：`src/content_aggregator/sources/collectors/douyin_hot_collector.py`

#### 目标 2：网易新闻
**现状**：未实现

**整合思路**：
- 直接复用 article-spider 的 `wangyi.py` 代码
- 适配 PROJECT-001 的 `BaseCollector` 接口
- 新增文件：`src/content_aggregator/sources/collectors/wangyi_collector.py`

#### 目标 3：微博热点
**现状**：未实现

**整合思路**：
- 参考 AIMedia 的微博爬虫
- 微博热搜接口：`https://weibo.com/ajax/side/hotSearch`（免登录）
- 新增文件：`src/content_aggregator/sources/collectors/weibo_hot_collector.py`

### 4.2 整合后的项目结构

```
content-aggregator/
├── src/content_aggregator/
│   ├── sources/
│   │   └── collectors/
│   │       ├── base_collector.py       # 基类（已有）
│   │       ├── douyin_collector.py     # 用户视频（已有）
│   │       ├── douyin_hot_collector.py # 🔥 新增：抖音热点榜
│   │       ├── wangyi_collector.py     # 🔥 新增：网易新闻
│   │       └── weibo_hot_collector.py  # 🔥 新增：微博热点
│   │       ├── rss_collector.py        # 已有
│   │       ├── youtube_collector.py    # 已有
│   │       └── ...
```

### 4.3 配置新增（config.yaml）

```yaml
sources:
  douyin_hot:
    enabled: true
    cookie: null  # 可选，热榜可免登录
    limit: 20     # 每次抓取热榜前 N 条
  
  wangyi:
    enabled: true
    channels: ["ent", "news", "tech"]  # 娱乐/新闻/科技
    interval_minutes: 30
    limit: 10
  
  weibo_hot:
    enabled: true
    limit: 30     # 微博热搜榜通常 50 条
```

### 4.4 代码整合工作量评估

| 采集器 | 工作量 | 难度 | 说明 |
|--------|--------|------|------|
| 抖音热点榜 | ~200 行 | ⭐⭐ | 需研究热榜 API 结构，适配 BaseCollector |
| 网易新闻 | ~100 行 | ⭐ | 直接移植 article-spider 的 wangyi.py |
| 微博热点 | ~150 行 | ⭐⭐ | 微博接口较简单，但需处理分页 |

**总计**：约 450 行新代码，1-2 天可完成。

---

## 五、为什么不整合 AIMedia 的其他模块？

| AIMedia 模块 | 是否整合 | 原因 |
|-------------|---------|------|
| Django 后端 | ❌ | PROJECT-001 已用 FastAPI，重复建设 |
| PySide6 桌面端 | ❌ | PROJECT-001 已有 Web UI，更灵活 |
| AI 内容生成 | ❌ | PROJECT-001 已有 6 种改写策略 |
| AI 图像生成 | ❌ | 超出 PROJECT-001 范围 |
| 多平台发布 | ❌ | 超出 PROJECT-001 范围 |
| 微信支付/登录 | ❌ | 超出 PROJECT-001 范围 |
| article-spider 爬虫逻辑 | ✅ | **轻量、可移植、正好需要** |
| 防封机制 | ⚠️ 可选 | PROJECT-001 已有 anti_block.py，可复用 |

---

## 六、执行建议

### 阶段 1：网易新闻（最快，1 天）
1. 克隆 article-spider 的 `wangyi.py`
2. 适配为 PROJECT-001 的 `BaseCollector` 子类
3. 更新 `collectors/__init__.py` 注册
4. 更新 config.yaml 添加配置项
5. 测试验证

### 阶段 2：微博热点（1 天）
1. 研究微博热搜 API 结构
2. 实现 `weibo_hot_collector.py`
3. 适配 BaseCollector 接口
4. 测试验证

### 阶段 3：抖音热点榜（1-2 天）
1. 研究抖音热榜 API（可能需要 Cookie）
2. 实现 `douyin_hot_collector.py`
3. 与现有 douyin_collector 区分（一个是用户视频，一个是热榜）
4. 测试验证

---

## 七、风险提示

1. **抖音/微博 API 变动频繁**：这两个平台的接口经常调整，需要定期维护
2. **反爬策略**：抖音热点可能需要 Cookie 才能稳定获取，建议先尝试免登录
3. **网易新闻**：相对最稳定，推荐优先实现
4. **不要过度设计**：保持轻量，每个采集器控制在 200 行以内
