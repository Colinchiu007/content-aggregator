# newsnow 项目分析报告

## 一、产品定位与核心思路

### 产品定位
**「优雅地阅读实时热点新闻」** — 一个聚焦实时热点的新闻聚合阅读器。

### 核心思路
| 维度 | 思路 |
|------|------|
| **内容范围** | 实时热点（realtime）+ 最热榜单（hottest），不追求全量，只做热点 |
| **栏目设计** | 7 个栏目：国内、国际、科技、财经、关注、实时、最热 |
| **更新策略** | 自适应抓取间隔（最小 2 分钟），根据源更新频率动态调整，防 IP 封禁 |
| **缓存策略** | 默认 30 分钟缓存；登录用户可强制刷新 |
| **用户系统** | GitHub OAuth 登录，登录后数据同步（Cloudflare D1） |
| **部署方式** | Cloudflare Pages 边缘部署（全球访问快），支持 Docker 本地部署 |
| **MCP 接入** | 支持 MCP Server，可作为 AI 工具的数据源 |

### 与 PROJECT-001 的差异
| 维度 | newsnow | PROJECT-001（热文采集改写） |
|------|----------|---------------------------|
| 核心功能 | 实时热点聚合阅读 | 热文采集 → AI 改写 → 多平台发布 |
| 内容处理 | 纯聚合，不改写 | 采集 + AI 改写 + SEO 优化 |
| 目标用户 | 新闻阅读者 | 内容创作者、公众号运营者 |
| 技术栈 | React+H3+Cloudflare | Python+FastAPI+Jinja2 |
| 数据源 | RSS + 热点榜单 API | RSS + 热点榜单 + 自定义链接 |
| 发布能力 | 无 | 支持微信公众号等多平台一键发布 |

---

## 二、技术实现分析

### 技术栈
```
前端：React 19 + @tanstack/react-router + framer-motion + UnoCSS
后端：H3（轻量 HTTP 框架，兼容 Node/Cloudflare Workers）
数据库：better-sqlite3（本地开发）+ Cloudflare D1（生产）
构建：Vite + pnpm
部署：Cloudflare Pages（静态）+ Cloudflare Worker（API）
```

### 关键实现细节

#### 1. 源定义系统
- 源定义在 `shared/sources`（TypeScript），通过 `scripts/source.ts` 预生成 `sources.json`
- 每个源有：`name`、`title`、`column`（所属栏目）、`type`（realtime/hottest）、`redirect`（是否重定向）
- 栏目-源关联关系在 `shared/metadata.ts` 中动态生成

#### 2. 自适应抓取
- 根据源更新频率动态调整抓取间隔（最小 2 分钟）
- 目的：节省资源 + 防止被封 IP

#### 3. 缓存机制
- 默认 30 分钟缓存
- 登录用户可通过 UI 强制刷新

#### 4. GitHub OAuth
- 使用 `jose` 库做 JWT 认证
- 首次运行需 `INIT_TABLE=true` 初始化数据库

#### 5. MCP Server
- 支持通过 MCP 协议暴露新闻数据给 AI 工具
- 可自建或直接用官方实例

---

## 三、可复用性评估

### 代码复用：**低** ⭐⭐
| 原因 | 说明 |
|------|------|
| 技术栈完全不同 | newsnow = TypeScript/React/H3/Cloudflare；PROJECT-001 = Python/FastAPI/Jinja2 |
| 运行环境不同 | Edge Runtime vs 传统服务器 |
| 数据模型不同 | SQLite vs Cloudflare D1 |

**结论**：直接复用代码不可行，但可以参考**架构思路**。

---

### 产品思路复用：**中** ⭐⭐⭐⭐
以下思路值得 PROJECT-001 借鉴：

#### 1. 栏目/分类系统
newsnow 的 7 栏目设计简洁实用：
```
国内 | 国际 | 科技 | 财经 | 关注 | 实时 | 最热
```
PROJECT-001 可以借鉴：
- 在 Web UI 中增加「栏目/标签」筛选
- 「实时」和「最热」可以作为排序选项（已有 sort=hot/recent）

#### 2. 缓存策略
newsnow 的 30 分钟缓存 + 强制刷新机制很实用。
PROJECT-001 可以加入：
- 采集结果缓存（避免重复采集同一 URL）
- 改写结果缓存（相同原文不重复改写）

#### 3. 用户登录/数据同步
newsnow 用 GitHub OAuth，简单且开发者友好。
PROJECT-001 已有 JWT Auth，可以扩展为：
- 支持 OAuth（GitHub/Google）作为登录选项
- 用户的改写历史、自定义策略云端同步

#### 4. 实时更新机制
newsnow 的「实时」栏目 + 自适应抓取间隔设计很好。
PROJECT-001 可以加入：
- WebSocket 推送改写进度（已有 `broadcast_ws`，可以扩展）
- 首页显示「最近采集/改写」动态

#### 5. MCP Server 接入
newsnow 支持 MCP，让 AI 工具能直接读取新闻数据。
PROJECT-001 可以同样做 MCP Server：
- 暴露「最近热文」、「改写结果」给 AI 工具
- 让 AI 助手能直接调用改写能力

---

### 数据源复用：**高** ⭐⭐⭐⭐⭐
**这是最有价值的复用点。**

newsnow 支持的中文信息源列表，可以直接参考来扩充 PROJECT-001 的采集能力：

#### 已确认 newsnow 支持的源（从代码结构推断）
| 类型 | 示例 |
|------|------|
| RSS 订阅 | 少数派、阮一峰、36氪 等 |
| 热点榜单 | 微博热点、抖音热点、知乎热榜 |
| 国际新闻 | 需要确认具体源 |

PROJECT-001 目前已支持：RSS、YouTube、Twitter、Douyin、网易、微博热点、抖音热点。

**建议**：把 newsnow 的源列表扒下来，直接补到 PROJECT-001 的 `config.yaml` 中。

---

### UI/UX 设计参考：**中** ⭐⭐⭐
newsnow 的 UI 关键词：**简洁、优雅、专注阅读**。

PROJECT-001 的前端是功能性页面（采集、改写、发布），可以参考 newsnow 的设计语言来做「阅读/预览」页面。

---

## 四、具体行动建议

### 高优先级（可立即执行）
1. **扒 newsnow 的源列表** → 补充到 PROJECT-001 的 `config.yaml`
   - 需要 clone repo，读 `shared/sources` 目录
   - 预计增加 10-20 个高质量中文信息源

2. **加入缓存机制**
   - 采集缓存：同一 URL 30 分钟内不重复采集
   - 改写缓存：相同原文（SimHash 匹配）不重复改写

### 中优先级（可后续迭代）
3. **栏目/分类系统**
   - Web UI 增加标签筛选（科技/财经/娱乐...）
   - 与改写策略联动（不同栏目用不同改写风格）

4. **MCP Server**
   - 让 AI 工具能读取 PROJECT-001 的改写结果
   - 技术栈：Python MCP SDK（官方已支持）

### 低优先级（长期规划）
5. **OAuth 登录**
   - 在现有 JWT 基础上，增加 GitHub/Google OAuth 选项

6. **实时推送**
   - WebSocket 推送采集/改写进度
   - 首页动态刷新

---

## 五、总结

| 维度 | 可复用性 | 说明 |
|------|----------|------|
| 代码 | ⭐⭐ | 技术栈完全不同，无法直接复用 |
| 产品思路 | ⭐⭐⭐⭐ | 栏目设计、缓存策略、实时更新机制值得借鉴 |
| 数据源 | ⭐⭐⭐⭐⭐ | **最有价值**，newsnow 的中文信息源列表可以直接参考 |
| UI/UX | ⭐⭐⭐ | 设计语言可以参考，特别是阅读页面 |
| 架构思路 | ⭐⭐⭐ | Edge Runtime 部署、自适应抓取等思路有启发 |

**最核心的复用点**：把 newsnow 的中文信息源列表扒下来，补充到 PROJECT-001，立即提升采集覆盖面。

---

*分析时间：2026-06-15 02:54 GMT+8*
*分析者：QClaw（CEO）*
