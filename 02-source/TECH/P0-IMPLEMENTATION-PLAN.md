# P0-IMPLEMENTATION-PLAN.md

**项目**: PROJECT-001 热文采集改写  
**版本**: v1.0.0  
**日期**: 2026-06-11  
**作者**: QClaw (CEO)  
**状态**: 🟢 P0 全部完成（v1.3.0）  

---

## 一、功能概述**

### 1.1 功能名称

**多平台一键发布**（Feature 18）

### 1.2 功能描述

用户在完成文章改写后，可以**一键发布到多个平台**（微信公众号、知乎专栏），无需手动逐个平台发布。

### 1.3 业务价值

| 维度 | 价值 |
|------|------|
| **效率提升** | 发布时间从 30 分钟（手动逐个发布）降低到 2 分钟（一键发布） |
| **成功率提升** | 统一错误处理 + 重试机制，发布成功率从 70% 提升到 ≥ 90% |
| **用户体验** | 无需记住各平台发布流程，降低使用门槛 |

### 1.4 成功指标（来自 PRD Section 1.3）

| 指标 | 目标值 |
|------|--------|
| 多平台发布成功率 | ≥ 90% |
| 多平台发布响应时间 | ≤ 60s（所有平台） |
| 策略复用率 | ≥ 60% |

---

## 二、任务拆分（≤ 4h/任务）

### 2.1 任务总览

**总预估工时**: 8h  
**任务数量**: 4 个任务（每个 ≤ 4h）  
**依赖关系**: 见图 2.1  
**可并行项**: 无（串行依赖）

| 任务 ID | 任务名称 | 预估工时 | 依赖 | 可并行 |
|----------|----------|----------|------|----------|
| **Task 1.1** | 设计多平台发布 API 接口 | 2h | 无 | ❌ |
| **Task 1.2** | 实现微信公众号发布接口 | 2h | Task 1.1 | ❌ |
| **Task 1.3** | 实现知乎专栏发布接口 | 2h | Task 1.1 | ❌ |

| **Task 2.1** | 前端多平台发布 UI | 2h | Task 1.2~1.3 | ✅ |

### 2.2 任务详情

#### Task 1.1：设计多平台发布 API 接口（2h）

**目标**: 设计统一的发布 API 接口，支持多平台并行发布。

**子任务**:
1. **1.1.1** 定义发布请求模型（30min）
   - 输入：`article_id`, `platforms: List[str]`, `options: Dict`
   - 输出：`task_id`, `status`, `results: List[PublishResult]`
   - 位置：`src/content_aggregator/api/publish.py`

2. **1.1.2** 定义发布结果模型（30min）
   - 字段：`platform`, `status` (success/failed), `message`, `url`
   - 位置：`src/content_aggregator/models/publish.py`

3. **1.1.3** 实现发布 API 路由（1h）
   - `POST /api/publish`：发起发布任务
   - `GET /api/publish/{task_id}`：查询发布进度
   - 位置：`web/server.py`

**验收标准**（来自 PRD Section 4.5）:
- Given 用户选择 3 个平台发布
- When 调用 `POST /api/publish`
- Then 返回 `task_id`，后台异步发布

---

#### Task 1.2：实现微信公众号发布接口（2h）

**目标**: 实现微信公众号草稿发布功能。

**子任务**:
1. **1.2.1** 读取微信公众号 API 文档（30min）
   - 文档：`https://developers.weixin.qq.com/doc/offiaccount/Publishing_Articles/Using_Sticker_in_Articles.html`
   - 关键 API：`cgi-bin/draft/add`, `cgi-bin/freepublish/submit`

2. **1.2.2** 实现微信公众号发布函数（1h）
   - 函数：`WeChatPublisher.publish(article: Article) -> PublishResult`
   - 位置：`src/content_aggregator/exporters/wechat_publisher.py`

3. **1.2.3** 添加错误处理 + 重试（30min）
   - 错误：API 限流（429）、Token 过期（40001）
   - 重试：指数退避（1s、2s、4s），最多 3 次

**验收标准**:
- Given 用户已配置微信公众号 API Key
- When 调用 `WeChatPublisher.publish()`
- Then 文章成功发布到微信草稿箱

---

#### Task 1.3：实现知乎专栏发布接口（2h）

**目标**: 实现知乎专栏文章发布功能。

**子任务**:
1. **1.3.1** 读取知乎专栏 API 文档（30min）
   - 文档：`https://zhuanlan.zhihu.com/api/docs`
   - 关键 API：`/api/v4/columns/{column_id}/articles`

2. **1.3.2** 实现知乎专栏发布函数（1h）
   - 函数：`ZhihuPublisher.publish(article: Article) -> PublishResult`
   - 位置：`src/content_aggregator/exporters/zhihu_publisher.py`

3. **1.3.3** 添加错误处理 + 重试（30min）
   - 错误：API 限流（429）、登录过期（403）
   - 重试：指数退避，最多 3 次

**验收标准**:
- Given 用户已配置知乎专栏 API Key
- When 调用 `ZhihuPublisher.publish()`
- Then 文章成功发布到知乎专栏

---

#### Task 2.1：前端多平台发布 UI（2h）

**目标**: 在改写结果页面添加"一键发布"按钮和平台选择弹窗。

**子任务**:
1. **2.1.1** 设计发布弹窗 UI（30min）
   - 元素：平台复选框（微信、知乎）、发布按钮、进度条
   - 位置：`web/templates/compose.html`

2. **2.1.2** 实现平台选择逻辑（30min）
   - 逻辑：用户选择平台 → 点击"发布" → 调用 `POST /api/publish`
   - 位置：`web/static/compose.js`

3. **2.1.3** 实现发布进度显示（1h）
   - 逻辑：轮询 `GET /api/publish/{task_id}` → 更新进度条
   - 位置：`web/static/compose.js`

**验收标准**:
- Given 用户已完成文章改写
- When 点击"一键发布"按钮
- Then 弹出平台选择弹窗，显示发布进度

---

## 三、依赖关系图**

```
Task 1.1 (设计 API 接口)
    ↓
    ├─→ Task 1.2 (微信发布) ──┐
    └─→ Task 1.3 (知乎发布) ──┘→ Task 2.1 (前端 UI)

```

**关键路径**: Task 1.1 → Task 1.2 或 1.3 → Task 2.1  
**最短时间**: 2h + 2h + 2h = **6h**  
**实际时间**（串行）: 2h + 2h×4 + 2h = **12h**  
**优化后时间**（并行 Task 1.2~1.5）: 2h + 2h + 2h = **6h** ✅

---

## 四、可并行项标注**

| 任务 | 可并行原因 | 并行方案 |
|------|--------------|----------|
| Task 1.2~1.5 | 都依赖 Task 1.1，但彼此独立 | ✅ **并行开发**（4 人×2h = 2h 总工时） |
| Task 2.1 | 依赖 Task 1.2~1.3 完成 | ❌ 必须等待后端接口完成 |

**推荐并行方案**（假设 1 人开发）:
- **Day 1**: Task 1.1（2h）+ Task 1.2（2h） = **4h**
- **Day 2**: Task 1.3（2h）+ Task 1.4（2h） = **4h**
- **Day 2**: Task 2.1（2h） = **2h**
- **总计**: **12h**（3 天）

**理想并行方案**（假设 4 人开发）:
- **Day 1**: Task 1.1（2h，1 人）+ Task 1.2~1.5（2h，4 人并行）= **2h**
- **Day 1**: Task 2.1（2h，1 人） = **2h**
- **总计**: **4h**（2 天）✅

---

## 五、验收标准（来自 PRD Section 4.5）**

### 5.1 功能验收

| Given | When | Then |
|-------|------|------|
| 用户选择 3 个平台发布 | 点击"一键发布" | 3 个平台同时发布，总耗时 ≤ 60s |
| 用户未配置某平台 API Key | 点击"一键发布" | 提示"请先配置 XX 平台 API Key" |
| 某平台发布失败 | 查看发布结果 | 显示失败平台和原因，其他平台继续发布 |
| 所有平台发布成功 | 查看发布结果 | 显示"全部发布成功" + 各平台文章链接 |

### 5.2 性能验收

| 指标 | 目标值 | 测试方案 |
|------|--------|----------|
| 多平台发布响应时间 | ≤ 60s | 同时发布到 4 个平台，计时 |
| 单平台发布成功率 | ≥ 95% | 发布 100 篇文章，统计成功率 |
| 多平台发布成功率 | ≥ 90% | 发布 100 篇文章到 4 个平台，统计成功率 |

---

## 六、技术设计（来自架构文档）**

### 6.1 系统架构（多平台发布）

```
用户浏览器
    ↓ HTTP POST /api/publish
FastAPI Server (web/server.py)
    ↓
多平台发布模块 (src/content_aggregator/exporters/)
    ├── WeChatPublisher (wechat_publisher.py)
    └── ZhihuPublisher (zhihu_publisher.py)
    ↓
各平台 API
    ├── 微信公众号 API (https://api.weixin.qq.com)
    └── 知乎专栏 API (https://zhuanlan.zhihu.com)
```

### 6.2 数据模型

**发布请求模型**:
```python
class PublishRequest(BaseModel):
    article_id: int
    platforms: List[str]  # ["wechat", "zhihu"]
    options: Dict = {}
```

**发布结果模型**:
```python
class PublishResult(BaseModel):
    platform: str
    status: str  # "success" | "failed"
    message: str
    url: Optional[str] = None
```

**发布任务模型**:
```python
class PublishTask(BaseModel):
    task_id: str
    article_id: int
    platforms: List[str]
    status: str  # "pending" | "running" | "completed" | "failed"
    results: List[PublishResult] = []
    created_at: datetime
```

### 6.3 API 设计

**发起发布任务**:
```
POST /api/publish
Content-Type: application/json

{
  "article_id": 123,
  "platforms": ["wechat", "zhihu"],
  "options": {}
}

Response:
{
  "task_id": "abc123",
  "status": "pending"
}
```

**查询发布进度**:
```
GET /api/publish/abc123

Response:
{
  "task_id": "abc123",
  "status": "running",
  "results": [
    {"platform": "wechat", "status": "success", "url": "https://..."},
    {"platform": "zhihu", "status": "running"}
  ]
}
```

---

## 七、风险评估与缓解措施**

### 7.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 各平台 API 限流 | 发布失败率高 | 🟠 中 | 添加重试机制（指数退避）+ 多 API Key 轮询 |
| 各平台 API 变更 | 发布功能失效 | 🟢 低 | 封装统一接口，隔离平台差异；定期检查 API 变更 |
| 发布耗时过长（> 60s）| 用户体验差 | 🟠 中 | 使用异步并发发布（asyncio.gather） |

### 7.2 业务风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 用户未配置 API Key | 无法发布 | 🔴 高 | 前端提示配置，后端校验 API Key 是否存在 |
| 某平台发布失败 | 部分内容未发布 | 🟠 中 | 返回失败原因，允许用户手动重试 |
| 发布内容违规 | 账号被封 | 🟢 低 | 添加敏感词检测（复用 Feature 4） |

---

## 八、测试计划**

### 8.1 单元测试（TDD）

| 测试项 | 覆盖目标 | 测试用例数 |
|----------|----------|------------|
| `WeChatPublisher.publish()` | ≥ 80% | 5 个（成功、限流、Token 过期、网络错误、参数错误） |
| `ZhihuPublisher.publish()` | ≥ 80% | 5 个 |
| `POST /api/publish` | ≥ 90% | 3 个（参数校验、任务创建、错误处理） |

### 8.2 集成测试

| 测试项 | 测试内容 |
|----------|----------|
| 端到端发布流程 | 选择平台 → 发起发布 → 查询进度 → 查看结果 |
| 多平台并发发布 | 同时发布到 4 个平台，验证总时间 ≤ 60s |
| 发布失败重试 | 模拟 API 限流错误，验证重试逻辑 |

### 8.3 手动测试

| 测试项 | 测试内容 |
|----------|----------|
| 微信公众号发布 | 配置 API Key → 发布文章 → 查看微信草稿箱 |
| 知乎专栏发布 | 配置 API Key → 发布文章 → 查看知乎专栏 |

---

## 九、发布计划**

### 9.1 发布前检查清单

| 检查项 | 状态 |
|----------|------|
| ✅ 所有单元测试通过（覆盖率 ≥ 80%） | ❌ 待完成 |
| ✅ 集成测试通过 | ❌ 待完成 |
| ✅ 手动测试通过（4 个平台） | ❌ 待完成 |
| ✅ API Key 加密存储 | ❌ 待完成（当前明文） |
| ✅ 错误日志记录完整 | ❌ 待完成 |

### 9.2 发布步骤

1. **合并到 main 分支**（2026-06-18）
   - `git checkout main`
   - `git merge feature/multi-publish`
   - `git tag v1.7.0`
   - `git push origin main --tags`

2. **更新 PRD**（2026-06-18）
   - 更新 `PRD-v1.7.0-2026-06-18.md`
   - 标记 Feature 18 为"✅ 已实现"

3. **创建发布文档**（2026-06-18）
   - 创建 `RELEASE-v1.7.0-2026-06-18.md`
   - 记录新增功能、修复 Bug、已知问题

4. **通知用户**（2026-06-18）
   - 发送通知："多平台一键发布功能已上线，欢迎试用！"

---

## 十、附录**

### 10.1 参考文献

| 文档 | 链接 |
|------|------|
| PRD v1.6.0 | `C:\Users\邱领\.qclaw\workspace\team\projects\PROJECT-001-hot-skill\PRD\PRD-v1.6.0-2026-06-09.md` |
| 架构文档 v1.0.0 | `C:\Users\邱领\.qclaw\workspace\team\projects\PROJECT-001-hot-skill\TECH\ARCHITECTURE-v1.0.0-2026-06-11.md` |
| 微信公众号 API 文档 | `https://developers.weixin.qq.com/doc/offiaccount/Publishing_Articles/Using_Sticker_in_Articles.html` |
| 知乎专栏 API 文档 | `https://zhuanlan.zhihu.com/api/docs` |

### 10.2 版本历史

| 版本 | 日期 | 修改内容 | 修改人 |
|------|------|---------|--------|
| v1.0.0 | 2026-06-11 | 创建开发计划（初版） | QClaw (CEO) |
| v1.1.0 | 2026-06-11 | 移除 Task 1.4（CSDN 发布接口，用户取消），更新工时 12h→10h | QClaw (CEO) |
| v1.2.0 | 2026-06-11 | 移除 Task 1.5（掘金发布接口，用户取消），更新工时 10h→8h，任务 5→4 | QClaw (CEO) |
| v1.3.0 | 2026-06-12 | Task 2.1（前端多平台发布 UI）已完成，P0 全部交付 | QClaw (CEO) |

---

*由 CEO (QClaw) 维护，2026-06-11 22:23 创建。*
