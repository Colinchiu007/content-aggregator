# Content Aggregator 功能迭代 PRD - v1.7.0

> **创建日期**：2026-06-12  
> **创建人**：QClaw (CEO)  
> **审批人**：QClaw (CEO)  
> **状态**：已审批  
> **审批日期**：2026-06-12  
> **关联项目**：PROJECT-001（热文采集改写平台）

> 📝 **版本说明**：本版本从 Y2A-Auto 项目移植经生产验证的 LLM 响应处理工具和 YouTube 错误诊断。修复了 LLM 改写反复输出推理内容、YouTube 错误信息不明确的已知问题。

---

## 一、背景与目标

### 1.1 背景

当前内容创作团队在热文采集和改写过程中存在以下痛点：
- 小红书/抖音等平台内容需手动整理，效率低
- 改写策略通用，无法按行业语境调整
- 内置策略固定，无法自定义保存
- 认证系统不统一，多项目无法复用
- 前端界面需要现代化改造
- 微信发布流程需要完善（封面管理、密码找回等）
- 多平台发布需要手动操作，效率低
- YouTube 字幕提取失败时无有效 fallback
- 缺少任务取消功能
- 代理配置硬编码，切换代理软件后需手动修改
- YouTube 采集排序固定，无法按需求调整

### 1.2 目标

- 支持链接采集（小红书/抖音）并自动转写文案
- 支持行业定向改写，提升输出专业度
- 支持自定义改写策略管理，提升复用率
- 统一认证系统，支持多项目复用
- 完善微信发布流程（封面管理、密码找回）
- 优化前端界面和用户体验
- 支持多平台一键发布，提升发布效率
- 优化 YouTube 字幕提取 fallback 逻辑
- 实现忘记密码功能
- 新增任务取消功能
- 优化代理配置自动检测
- **新增**：支持 YouTube 采集排序选项配置

### 1.3 成功指标

| 指标 | 目标值 |
|------|--------|
| 内容产出效率 | 提升 50%（篇/小时）|
| 改写质量满意度 | ≥ 85% |
| 策略复用率 | ≥ 60% |
| 用户认证成功率 | ≥ 99% |
| 微信发布成功率 | ≥ 95% |
| 多平台发布成功率 | ≥ 90% |
| YouTube 字幕提取成功率 | ≥ 95% |
| YouTube 采集排序灵活性 | 支持 4 种排序方式 |

---

## 二、用户故事

| 用户角色 | 场景 | 需求 |
|----------|------|------|
| 内容创作者 | 看到小红书/抖音爆款视频 | 希望粘贴链接直接获取文案，以免去手动整理 |
| 行业从业者 | 需要发布专业内容 | 希望改写时能指定目标行业，使输出更专业 |
| 重度用户 | 有多种改写风格需求 | 希望能保存多份改写策略并设默认，提升效率 |
| 系统管理员 | 管理多项目用户 | 希望统一认证系统，避免重复开发 |
| 微信公众号运营 | 发布文章到微信 | 希望完善封面管理、密码找回等功能 |
| 前端开发者 | 维护前端界面 | 希望现代化前端设计，提升用户体验 |
| 多平台运营 | 发布文章到多个平台 | 希望一键发布到多个平台，减少手动操作 |
| YouTube 内容创作者 | 采集 YouTube 视频字幕 | 希望字幕提取失败时能获取任意可用字幕 |
| 普通用户 | 忘记密码 | 希望可以通过邮箱重置密码 |
| 任务管理者 | 管理运行中的任务 | 希望可以取消 pending/running 状态的任务 |
| 技术支持 | 配置代理 | 希望系统能自动检测可用代理端口 |
| YouTube 采集者 | 采集 YouTube 视频 | 希望可以配置采集排序方式（最新、播放量、评分、相关性）|

---

## 三、功能列表

### 3.1 已发布功能（v1.1.0 ~ v1.5.0）

| 功能 | 版本 | 状态 |
|------|------|------|
| 链接采集（小红书/抖音）| v1.1.0 | ✅ 已实现 |
| 文章改写-行业定向 | v1.1.0 | ✅ 已实现 |
| 文章改写-策略管理 | v1.1.0 | ✅ 已实现 |
| 微信公众号文章采集 | v1.2.0 | ✅ 已实现 |
| 知乎专栏采集 | v1.2.0 | ✅ 已实现 |
| 微信公众号草稿发布 | v1.2.0 | ✅ 已实现 |
| 统一认证系统复用 | v1.3.0 | ✅ 已实现 |
| 封面选择集成到排版发布弹窗 | v1.3.0 | ✅ 已实现 |
| 图片模型设置页面 | v1.3.0 | ✅ 已实现 |
| 前端重设计「信息实验室」| v1.3.0 | 🚧 待实现 |
| 非中文内容自动翻译并改写 | v1.4.0 | ✅ 已实现 |
| API Key 预览功能 | v1.3.0 | ✅ 已实现 |
| 封面发布优先级链 | v1.3.0 | ✅ 已实现 |
| 默认封面管理 API + UI | v1.3.0 | ✅ 已实现 |
| 默认封面 media_id 缓存优化 | v1.3.0 | ✅ 已实现 |
| 发布报错修复 | v1.3.0 | ✅ 已修复 |
| 多平台一键发布 | v1.5.0 | 🚧 待实现 |
| YouTube 字幕提取 Fallback | v1.5.0 | 🚧 待实现 |
| 忘记密码功能实现 | v1.5.0 | 🚧 待实现 |
| 任务取消功能 | v1.5.0 | 🚧 待实现 |
| 代理配置自动检测优化 | v1.5.0 | 🚧 待实现 |

### 3.2 新增功能（v1.6.0）

| 功能 | 优先级 | 状态 |
|------|--------|------|
| YouTube 采集排序选项 | P1 | 🚧 待实现 |

---

## 四、功能详情

### 功能 24：YouTube 采集排序选项

#### 4.1 需求背景

当前 YouTube 数据采集时，排序方式固定（默认为播放量排序），无法根据需求调整为最新、评分或相关性排序，限制了采集灵活性。

#### 4.2 实现方式

**修改文件**：
- `web/templates/settings.html`：在数据源设置页面的 YouTube 部分增加排序选项
- `config/config.yaml`：新增 `youtube.search_order` 配置项
- `src/content_aggregator/sources/collectors/youtube_collector.py`：读取配置中的排序选项

**配置示例**：
```yaml
youtube:
  search_order: viewCount  # 可选值：date, viewCount, rating, relevance，默认为 viewCount
```

**前端界面**：
- 在 YouTube 设置区域新增下拉框：
  - 选项：最新 (date)、播放量 (viewCount)、评分 (rating)、相关性 (relevance)
  - 默认值：播放量 (viewCount)
  - 提示文字："选择 YouTube 搜索结果的排序方式"

**后端逻辑**：
- 读取配置文件中的 `youtube.search_order`
- 在调用 YouTube Data API 的 `search().list()` 时，传入 `order` 参数
- 支持的排序方式：
  - `date`：按时间最新排序
  - `viewCount`：按播放量排序
  - `rating`：按评分排序
  - `relevance`：按相关性排序（默认）

#### 4.3 技术约束

| 项目 | 说明 |
|------|------|
| YouTube Data API | 使用 v3 版本，支持 `order` 参数 |
| 配置热更新 | 修改配置后无需重启，自动生效 |
| 默认值 | 播放量 (viewCount) |

#### 4.4 API 设计

**配置读取**：
- 读取路径：`config.config.yaml` 中的 `youtube.search_order`
- 默认值：`viewCount`

**API 调用示例**：
```python
youtube.search().list(
    part="snippet",
    q=query,
    type="video",
    order=config.youtube.search_order,  # 新增参数
    maxResults=max_results
)
```

#### 4.5 验收标准

- **Given** 用户在设置页面选择"最新"
  **When** 采集 YouTube 视频
  **Then** 搜索结果按上传时间最新排序

- **Given** 用户在设置页面选择"播放量"
  **When** 采集 YouTube 视频
  **Then** 搜索结果按播放量从高到低排序

- **Given** 用户未配置排序选项
  **When** 采集 YouTube 视频
  **Then** 使用默认排序（播放量）

- **Given** 用户在设置页面选择"评分"
  **When** 采集 YouTube 视频
  **Then** 搜索结果按评分从高到低排序

- **Given** 用户在设置页面选择"相关性"
  **When** 采集 YouTube 视频
  **Then** 搜索结果按与关键词的相关性排序

---

## 五、非功能需求

### 5.1 性能

| 指标 | 目标值 |
|------|--------|
| 页面加载时间 | ≤ 2s |
| API 响应时间 | ≤ 500ms（非 AI 调用）|
| AI 调用响应时间 | ≤ 30s |
| 多平台发布响应时间 | ≤ 60s（所有平台）|
| YouTube 采集响应时间 | ≤ 10s |

### 5.2 安全性

| 指标 | 目标值 |
|------|--------|
| API Key 加密存储 | 100% |
| JWT Token 有效期 | 7 天 |
| 密码找回 Token 有效期 | 1h |
| 多平台 API Key 隔离 | 各平台 API Key 独立存储 |
| YouTube API Key 隔离 | 独立存储 |

### 5.3 兼容性

| 指标 | 目标值 |
|------|--------|
| 浏览器兼容 | Chrome、Firefox、Safari、Edge 最新版本 |
| 移动端适配 | 响应式布局 |
| 平台 API 兼容 | 遵守各平台 API 规范 |
| YouTube Data API 兼容 | v3 |

---

## 六、风险与依赖

### 6.1 风险

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 微信 API 权限不足 | 无法发布文章到微信 | 提前确认账号权限 |
| 多平台 API 不稳定 | 发布失败率高 | 提供重试机制和错误日志 |
| YouTube API 限制 | 字幕提取失败 | 优化 Fallback 逻辑 |
| 代理检测误判 | 错误配置代理端口 | 增加检测超时和重试机制 |
| YouTube API 配额限制 | 采集失败 | 合理控制采集频率，使用缓存 |

### 6.2 依赖

| 依赖 | 说明 |
|------|------|
| 微信公众号 API | 发布文章到微信 |
| 知乎专栏 API | 发布文章到知乎 |
| YouTube Data API | 提取字幕、采集视频 |
| SMTP 服务 | 发送密码重置邮件 |

---

## 七、排期建议

| 功能 | 预估工时 | 优先级 |
|------|----------|--------|
| YouTube 采集排序选项 | 2h | P1 |
| 多平台一键发布 | 12h | P0 |
| YouTube 字幕提取 Fallback | 3h | P1 |
| 忘记密码功能实现 | 4h | P1 |
| 任务取消功能 | 4h | P1 |
| 代理配置自动检测优化 | 3h | P2 |
| **合计** | **28h** |  |

---

## 版本更新记录

| 版本 | 日期 | 修改内容 | 修改人 |
|------|------|---------|--------|
| v1.1.0 | 2026-06-01 | 创建文档（链接采集、行业定向改写、改写策略管理） | QClaw (senior-pm skill) |
| v1.1.1 | 2026-06-07 | 按 PRODUCT-DOCS-STANDARD 规范更新头部格式，移入标准目录 | QClaw (CEO) |
| v1.1.2 | 2026-06-07 | 补充缺失章节（背景与目标、用户故事、非功能需求、风险与依赖），添加批注待 PM 审核 | QClaw (CEO) |
| v1.2.0 | 2026-06-07 | 新增功能 4~6（微信公众号采集、知乎专栏采集、微信草稿发布），新增问题改进章节，新增技术债务章节 | QClaw (CEO) |
| v1.3.0 | 2026-06-07 | 合并 INBOX 所有待处理需求（2026-06-01 ~ 2026-06-07），新增功能 7~16，优化现有功能 | QClaw (CEO) |
| v1.4.0 | 2026-06-08 | 新增功能 17：非中文内容自动翻译并改写（由 senior-pm skill 按产品需求标准化流程输出） | QClaw (senior-pm skill) |
| v1.5.0 | 2026-06-08 | 合并 INBOX 待处理需求（2026-06-02 ~ 2026-06-08），新增功能 18~23 | QClaw (CEO) |
| v1.6.0 | 2026-06-09 | 合并 INBOX 待处理需求（2026-06-09），新增功能 24：YouTube 采集排序选项 | QClaw (CEO) |
| v1.7.0 | 2026-06-12 | 移植 Y2A-Auto LLM 响应处理工具集 + YouTube 错误诊断 + 任务断点续跑 + CookieCloud 集成（功能 25~29）| QClaw (CEO) |

### 3.3 v1.7.0 新增功能

| 功能 | 优先级 | 状态 |
|------|--------|------|
| LLM 推理输出防御（Y2A-Auto 移植）| P0 | ✅ 已实现 |
| 输入内容预清洗 | P0 | ✅ 已实现 |
| YouTube API 错误分级诊断 | P1 | ✅ 已实现 |
| 任务断点续跑（Checkpoint）| P2 | ✅ 已实现 |
| CookieCloud 集成 | P3 | ✅ 已实现 |

---

### 功能 25：LLM 推理输出防御系统（Y2A-Auto 移植）

#### 25.1 需求背景

当前使用推理模型（如 sensenova-6.7-flash-lite）时，LLM 输出频繁包含:
- 分析过程/提纲（Chain-of-Thought）
- 英文推理前缀（如 "Let me think about this..."）
- 模型返回 reasoning_content 字段而非 content

这些推理输出会完全破坏改写结果，用户看到的是英文分析而非正式文章。

#### 25.2 实现方式

**新增文件**:
- `src/content_aggregator/clients/llm_utils.py` — 从 Y2A-Auto 移植的核心工具函数

**核心功能**:

| 函数 | 来源 | 用途 |
|------|------|------|
| `strip_reasoning_thoughts()` | Y2A-Auto utils.py | 移除 `<think>...</think>` / ````think ...```` 等推理标签 |
| `extract_json_from_text()` | Y2A-Auto utils.py | 从任意 LLM 文本中解析 JSON，兼容代码块/包裹文本 |
| `clean_input_content()` | Y2A-Auto ai_enhancer._pre_clean | 去除 URL、邮箱、社交账号、CTA、赞助链接等噪点 |
| `build_thinking_disabled_body()` | Y2A-Auto utils.py | 在 API 请求中添加 `thinking: disabled` 参数 |

**三层防御机制**:
1. **请求层**：自动添加 `extra_body.thinking = disabled` 参数，尝试让推理模型直接输出最终答案
2. **响应层**：收到 LLM 响应后，用 `strip_reasoning_thoughts()` + `_is_reasoning_content()` 双重检测
3. **降级层**：若 API 不支持 `thinking` 参数（返回 422/unknown parameter），自动回退移除参数重试

**修改文件**:
- `src/content_aggregator/clients/llm_client.py` — 集成 thinking disabled 控制 + 响应简化
- `src/content_aggregator/processors/rewrite/rewriter.py` — 输入预清洗 + 推理标签清理升级
- `src/content_aggregator/processors/language_detector.py` — 使用 `extract_json_from_text()` 提升解析健壮性

#### 25.3 技术约束

| 项目 | 说明 |
|------|------|
| API 兼容性 | 通过 `has_thinking_param` 检测，仅对推理模型添加 `extra_body` |
| 降级策略 | API 报错时自动移除参数并重试 |
| 输入清洗 | 保留核心正文段（最多 3 段），不会过度截断 |

#### 25.4 验收标准

- **Given** 输入含推广内容/URL
  **When** 调用改写
  **Then** 正文无推广噪点

- **Given** LLM 返回 `<think>...</think>` 内容
  **When** 解析响应
  **Then** 推理标签被剥离，仅保留正文

- **Given** API 不支持 `thinking: disabled` 参数
  **When** 调用 API
  **Then** 自动回退，不影响功能

---

### 功能 26：输入内容预清洗

#### 26.1 需求背景

改写前的原文常包含:
- YouTube 描述中的推广链接/订阅号召
- 文章末尾的版权声明、来源链接
- 社交账号（@handle）和标签（#topic）

这些噪点会随正文一起提交给 LLM，导致改写结果被污染。

#### 26.2 实现方式

采用 `clean_input_content()` 函数在 `_build_prompt()` 中预先清洗：
1. 移除所有 URL（http/https/ftp/www）
2. 移除邮箱地址
3. 移除社交账号（@mention）和标签（#hashtag）
4. 移除赞助链接（Patreon/Ko-fi/BuyMeACoffee）
5. 移除 CTA 短语（"link in description"等）
6. 按段落检测推广密度，超过 50% 行是推广内容的段落整段跳过

保留核心正文段数：最多 3 段，保证内容完整性的同时去噪。

#### 26.3 验收标准

- **Given** 输入含推广行（"Subscribe to my channel"）
  **When** 调用改写
  **Then** 推广行从正文中移除

- **Given** 输入全部为推广内容
  **When** 调用改写
  **Then** 保留最少一段内容

---

### 功能 27：YouTube API 错误分级诊断

#### 27.1 需求背景

之前的 YouTube 错误处理过于简单（`resp.raise_for_status()`），用户只能看到 HTTP 状态码，无法区分配额耗尽、Key 无效、限速等不同场景。

#### 27.2 实现方式

从 Y2A-Auto `youtube_handler.py` 移植错误诊断函数，新增 `_classify_api_error()` 方法：

| HTTP 状态码 | 诊断 | 用户提示 |
|-------------|------|----------|
| 400 + keyInvalid | API Key 无效 | 提示检查 .env 中的 YOUTUBE_API_KEY |
| 403 + bot_challenge | 反机器人拦截 | 建议启用代理/换 Key/稍后再试 |
| 403 + quotaExceeded | 配额耗尽 | 提示第二天即可恢复 |
| 404 | 资源不存在 | 提示频道/视频已删除 |
| 429 | 速率限制 | 提示降低采集频率 |
| 5xx | 服务端错误 | 提示临时问题 |

**新增函数**:
- `looks_like_youtube_bot_challenge()` — 检测反机器人拦截
- `looks_like_format_selection_error()` — 检测格式选择失败
- `summarize_yt_error()` — 从输出中提取核心错误摘要

**修改文件**: `src/content_aggregator/sources/youtube.py`
- 替换所有 `resp.raise_for_status()` 为 `_classify_api_error()` 调用
- 改进 `connect()`/`_fetch_channel_videos()`/`_search_videos()` 错误处理

#### 27.3 验收标准

- **Given** API Key 无效
  **When** 调用 `connect()`
  **Then** 返回 "YouTube API Key 无效" 提示

- **Given** 配额耗尽
  **When** 调用 `collect()`
  **Then** 返回 "YouTube API 配额已耗尽" 提示

- **Given** 正常的 API 错误
  **When** 调用 `collect()`
  **Then** 返回包含 HTTP 状态码和原因描述的错误信息

---

### 功能 28：任务断点续跑（Checkpoint）

#### 28.1 需求背景

当前调度器（Scheduler）和流水线（Pipeline）完全是内存状态。如果服务器进程崩溃或重启：
- 正在执行的采集/改写任务状态全部丢失
- 已经处理完的 items 无法标记，下次会重复处理
- 用户无从得知哪些任务中断了

#### 28.2 实现方式

**新增文件**: `src/content_aggregator/workflows/task_store.py`（~660 行）

**数据模型（SQLite）**:

| 表 | 作用 |
|-----|------|
| `tasks` | 每次执行的任务记录，含进度/状态/错误 |
| `items` | 每个被处理的 content 项的流水线阶段和结果 |
| `checkpoint_log` | 阶段变更日志（可选项，用于调试）|

**流水线阶段**:

```
collected → filtered → rewriting → rewritten → completed
                ↓ failed          ↓ failed
              failed             failed
```

**恢复机制**:
- `get_interrupted_tasks()` — 查找 status=running/pending 但无活跃线程的任务
- `detect_and_prepare_recovery()` — 返回已完成（可跳过）和未完成（需重处理）的 items
- 进程崩溃后重启，可自动检测并恢复中断的任务

**并发控制**（从 Y2A-Auto 移植）:
- `mark_task_active()` / `is_task_active()` — 防止同一任务重复运行
- `request_task_cancel()` / `is_task_cancelled()` — 线程安全取消
- `should_reduce_concurrency()` — 内存 >80% 时降低并发

**集成点**:

| 组件 | 集成方式 |
|------|----------|
| `pipeline.py` | `process_contents()` 增加可选 task_store/task_id/item_ids/skip_ids 参数 |
| `pipeline.py` | `process_with_checkpoint()` — 带 checkpoint 的处理包装器 |
| `pipeline.py` | `process_all_sources_with_checkpoint()` — batch 包装器 |
| `pipeline.py` | `recover_interrupted_tasks()` — 静态恢复入口 |
| `scheduler.py` | `start()` 时检测并标记中断任务 |
| `scheduler.py` | `load_from_config()` 回调使用 `process_all_sources_with_checkpoint` |
| `scheduler.py` | `cancel_task()` — 暴露取消接口 |

#### 28.3 技术约束

| 项目 | 说明 |
|------|------|
| 存储 | SQLite WAL 模式，data/tasks.db，支持多线程并发 |
| 恢复粒度 | 单个 item 级别的 stage 追踪，不会部分恢复 LLM 调用 |
| 回退策略 | rewriting 状态的 items 回退到 rewritten 之前（LLM 调用不可恢复）|
| 错误处理 | 失败的 items 标记为 failed，不阻塞后续 items |
| 兼容性 | 不配置 TaskStore 时降级为内存模式，无影响 |

#### 28.4 验收标准

- **Given** 进程在处理过程中崩溃
  **When** 重启后调用 `recover_interrupted_tasks()`
  **Then** 检测到中断任务并返回可恢复 items 数量

- **Given** 同一任务触发两次
  **When** 第二次运行时
  **Then** `mark_task_active()` 返回 False，拒绝重复运行

- **Given** 正在运行的任务
  **When** 调用 `cancel_task()`
  **Then** `is_task_cancelled()` 返回 True，管道感知并中止

---

### 功能 29：CookieCloud 集成

#### 29.1 需求背景

YouTube Data API v3 有配额限制（每天 10000 单位），且无法访问年龄/地区限制内容。
如果后续使用 yt-dlp 采集 YouTube 视频，需要有效的浏览器 cookies 来绕过限制。

CookieCloud（https://github.com/easychen/CookieCloud）是一个开源工具：
1. 浏览器装 CookieCloud 扩展 → 定期将 cookies AES 加密后上传到自建服务器
2. 本模块加密拉取 → 解密 → 过滤 → 写入本地 Netscape 格式文件
3. yt-dlp 等工具通过 `--cookies` 参数使用

#### 29.2 实现方式

**新增文件**: `src/content_aggregator/sources/cookiecloud.py`（~500 行）

| 函数 | 说明 |
|------|------|
| `sync_youtube_cookies(settings)` | 一键同步入口（拉取→解密→过滤→写入）|
| `validate_settings()` | 配置校验（server_url/uuid/password 必填）|
| `fetch_payload()` | HTTPS 加密拉取 CookieCloud 服务器数据 |
| `decrypt_payload()` | AES-CBC 解密，4 种加密模式自动回退 |
| `extract_youtube_cookies()` | 过滤 youtube.com/youtu.be/google.com 域名 |
| `write_cookie_file()` | Netscape HTTP Cookie File 格式（yt-dlp 兼容）|

**加密模式（按尝试顺序）**:

| 模式 | Key 派生 | 描述 |
|------|----------|------|
| legacy | MD5(UUID+Password) | CookieCloud 原始协议 |
| legacy+pbkdf2 | PBKDF2-HMAC-SHA256 × 200000 | Preview 兼容增强 |
| aes-128-cbc-fixed | MD5(UUID+Password), IV=\x00×16 | 新协议 |
| aes-128-cbc-fixed+pbkdf2 | PBKDF2-HMAC-SHA256 × 200000 | Preview 兼容增强 |

#### 29.3 设计原则

- **独立模块**：不依赖 pipeline/scheduler，纯工具模块
- **零耦合**：导入即可用，不污染其他模块
- **默认禁用**：`config.yaml` 中 `cookiecloud.enabled: false`
- **优雅降级**：同步失败只写日志，不影响主流程
- **CLI 支持**：`python cookiecloud.py <server_url> <uuid> <password>` 可直接测试

#### 29.4 配置

```yaml
cookiecloud:
  enabled: false              # 是否启用
  server_url: ""               # CookieCloud 服务器地址
  uuid: ""                     # UUID
  password: ""                 # 密码
  output_path: "data/yt_cookies.txt"  # 输出路径
  allow_plaintext_export: true  # 允许明文导出
```

#### 29.5 验收标准

- **Given** 正确的 CookieCloud 配置
  **When** 调用 `sync_youtube_cookies(settings)`
  **Then** 返回包含 `success=True`、cookie 数量和文件路径

- **Given** 错误的配置（空 server_url）
  **When** 调用 `validate_settings()`
  **Then** 抛出 `ConfigError`

- **Given** disabled 状态
  **When** 任何组件调用 `load_config()`
  **Then** 返回 None，无副作用

---

## 八、审批记录

| 审批人 | 角色 | 审批日期 | 审批意见 |
|----------|------|----------|----------|
| QClaw | CEO | 2026-06-11 | 批准 v1.6.0 |
| QClaw | CEO | 2026-06-12 | 批准 v1.7.0（Y2A-Auto 技术整合：P0 LLM 防御 + P1 YouTube 诊断 + 断点续跑 + CookieCloud）|

**CEO 签字**：QClaw  
**日期**：2026-06-12  
**版本**：v1.7.0  
**状态**：已审批  

---

*本文档由 CEO (QClaw) 手动更新，符合产品资料管理规范（PRODUCT-DOCS-STANDARD v1.0.0）。*
