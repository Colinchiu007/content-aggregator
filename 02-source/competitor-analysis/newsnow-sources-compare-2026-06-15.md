# newsnow 源列表 vs PROJECT-001 对比报告

## 一、newsnow 源列表（47 个，按栏目）

### 国内（17 个）
知乎、微博、抖音、虎扑、百度贴吧、今日头条、澎湃新闻、哔哩哔哩、百度热搜、牛客、凤凰网、虫部落、豆瓣、腾讯新闻、Freebuf、腾讯视频、爱奇艺

### 国际（5 个）
联合早报、卫星通讯社、参考消息、靠谱新闻、Steam

### 科技（12 个）
V2EX、酷安、36氪、AIHOT、IT之家、远景论坛、Solidot、Hacker News、Product Hunt、GitHub、少数派、稀土掘金

### 财经（7 个）
MKTNews、华尔街见闻、财联社、雪球、格隆汇、法布财经、金十数据

---

## 二、PROJECT-001 现有源

| 类型 | 源 | 状态 |
|------|------|------|
| RSS | 少数派、阮一峰、Google Deepmind、36氪（disabled）| ✅ |
| 热点榜 | 微博热点、抖音热点榜 | ✅ |
| 视频 | YouTube（需 API Key）| ⚠️ |
| 社交 | Twitter（需 Bearer Token）| ⚠️ |
| 内容 | 网易新闻/娱乐/科技 | ✅ |
| 短视频 | 抖音（需 Cookie）| ⚠️ |
| 其他 | 知乎、虎扑、IT之家、华尔街见闻... | ❌ 未接入 |

---

## 三、可立即添加的源（RSS 或 API 可接入）

### 🟢 高价值 + 低难度（有 RSS 或公开 API）

| 源 | 类型 | 接入方式 | 备注 |
|------|------|----------|------|
| **知乎热榜** | 热点榜单 | 公开 API（`https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50`） | 无需登录 |
| **虎扑主干道** | 论坛热帖 | RSS 或网页爬取 |  |
| **36氪** | 科技资讯 | RSS（`https://36kr.com/feed`） | config 中已配置但 disabled |
| **IT之家** | 科技资讯 | RSS（`https://www.ithome.com/rss/`） |  |
| **华尔街见闻快讯** | 财经快讯 | 网页爬取或 API |  |
| **财联社电报** | 财经快讯 | 网页爬取 |  |
| **金十数据** | 财经实时 | 网页爬取 |  |
| **Hacker News** | 科技热点 | 官方 API（`https://hacker-news.firebaseio.com/v0/topstories.json`） | 无需登录 |
| **GitHub Trending** | 开发热点 | 网页爬取（`https://github.com/trending`） |  |

### 🟡 中价值 + 中难度（需要爬虫）

| 源 | 接入方式 | 难度 |
|------|----------|------|
| 微博热搜 | 网页爬取（需 Cookie 或模拟浏览器） | ⭐⭐⭐ |
| 抖音热点 | 网页爬取（需 Cookie） | ⭐⭐⭐⭐ |
| 百度热搜 | 网页爬取 | ⭐⭐ |
| 哔哩哔哩热搜 | 网页爬取或 API | ⭐⭐⭐ |
| 豆瓣热门电影 | 网页爬取 | ⭐⭐ |

### 🔴 低优先级（内容质量或覆盖面与现有源重叠）

酷安、贴吧、牛客、凤凰网、虫部落、腾讯新闻、Freebuf、Product Hunt、Steam...

---

## 四、具体行动建议

### ✅ 立即执行（30 分钟内可完成）

1. **启用 36氪 RSS**
   - `config.yaml` 中已配置 `enabled: false`，改为 `true` 即可

2. **添加 IT之家 RSS**
   ```yaml
   - name: "IT之家"
     rss_url: "https://www.ithome.com/rss/"
     column: "tech"
     enabled: true
   ```

3. **添加知乎热榜采集器**
   - 新建 `src/content_aggregator/sources/collectors/zhihu_collector.py`
   - API 端点：`https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50`
   - 无需登录，直接返回 JSON

### ⚙️ 本周内完成

4. **添加 Hacker News**
   - 官方 API 无需认证
   - 参考 `src/content_aggregator/sources/collectors/` 中现有采集器格式

5. **添加 GitHub Trending**
   - 网页爬取（`https://github.com/trending`）
   - 或使用 `github-trending-api` 第三方服务

6. **财经源（华尔街见闻/财联社/金十）**
   - 这三个是中文财经核心源，强烈建议接入
   - 华尔街见闻有 RSS：`<https://wallstreetcn.com/feed>`

### 📅 后续规划

7. **热点榜单爬虫框架**
   - 封装一个通用网页爬取框架（类似现有 `base_collector.py`）
   - 支持：微博热搜、百度热搜、抖音热点等

8. **「热点榜单」独立栏目**
   - 参考 newsnow 的 `hottest` 类型
   - 在 Web UI 中增加「热榜」Tab

---

## 五、与 newsnow 的差异化定位

| 维度 | newsnow | PROJECT-001 |
|------|----------|--------------|
| 核心功能 | 热点链接聚合（标题+URL） | 全文采集 + AI 改写 |
| 数据深度 | 浅（只有标题和热度） | 深（全文+改写+SEO） |
| 目标用户 | 新闻阅读者 | 内容创作者 |
| 发布能力 | 无 | 多平台一键发布 |

**结论**：不必追求覆盖 newsnow 的全部源，而是**挑选高质量源**（知乎、36氪、IT之家、华尔街见闻）接入，提升 PROJECT-001 的内容覆盖面。

---

## 六、源添加优先级排序

```
P0（立即）: 36氪(RSS已配置)、IT之家、知乎热榜
P1（本周）: Hacker News、GitHub Trending、华尔街见闻
P2（本月）: 财联社、金十数据、虎扑
P3（后续）: 微博热搜爬虫、抖音热点爬虫
```

---

*报告生成时间：2026-06-15 03:12 GMT+8*
*依据：newsnow/pre-sources.ts（47 个源定义）+ PROJECT-001/config.yaml（现有源）*
