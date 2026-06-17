# 2026-04-20：记忆系统启用

## 2026-05-11：多 Agent 团队体系建立

为用户建立了完整的 QClaw 智能团队架构：
- **团队目录**：`C:\Users\邱领\.qclaw\workspace\team\`
- **团队成员**：CEO（我）、CTO、PM、COO、Specialist
- **协作机制**：通过共享 Workspace + sessions_spawn 实现
- **关键文件**：team/README.md（总纲）、team/MANUAL.md（使用手册）
- **注意**：webchat 通道对 `mode="session"` 持久 Session 有限制，固定员工采用 `mode="run"` 隔离运行模式

## 2026-05-18：content-aggregator 项目从开发经理W接手

**来源**：agent-904355f2（开发经理W）的飞书会话（e8ce57e1），因孤儿 tool call 导致会话卡住无法继续。

**项目路径**：`C:\Users\邱领\.qclaw\workspace\content-aggregator\`
**对话导出**：`content-aggregator\conversation-export-e8ce57e1.md`（2783条消息，5/10~5/18）

### 项目概述：内容聚合器 / Tech News Digest

**技术栈**：Python FastAPI + Jinja2 多模板 Web UI

#### 已完成
| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | RSS采集 → AI改写 → 内容格式化 → 端到端测试 | ✅ |
| Phase 3 | 内容过滤（敏感词+去重） | ✅ |
| SEO | SEO元数据采集、API端点集成 | ✅ |

#### 核心结构
- `src/content_aggregator/` — 主模块（models, scheduler）
- `tools/` — collect, export, rewrite, seo
- `web/` — FastAPI server + Jinja2 模板（7个页面）
- `scripts/` — run.py, web.py, 测试脚本
- `config/` — YAML 配置

#### 未完成 / 待确认
- [ ] Web UI 与原始版本一致性（用户反馈有差异）
- [ ] Git 全局代理配置
- [ ] SEO 参数 `run.py --seo` 可能需检查

#### Git 最近 commits
- `8cfe5e1` test: 重写全流程测试脚本
- `3531d24` feat(pdf): 注册中文字体
- `61bd9d2` fix(seo): JSON解析修复
- `2140507` feat: 添加 OpenClaw 工具封装

## Promoted From Short-Term Memory (2026-05-25)

- 用户再次纠正：**PROJECT-001 是热文采集改写项目**，不是众神卡牌！ 用户原话："不是，你还是搞错了，PROJECT-001，是之前说的热文采集改写项目，是另一个agent在开发的。但我在对话里没找到历史记录。是不是上下文的长度满了？失去记忆了？" ### 发现真相 读取 `team/memory/TEAM.md`，发现正确记录： > | 热文改写 Skill 评估 | **PROJECT-001** | 🔵 立项，阶段1 | team/deliverables/hot-skill/ | ### 正确的项目清单（最终版） | 项目ID | 项目名称 | 状态 | 路径 | 开发者 | |---------|----------|------|------|--------| | **PROJECT-001** | 热文采集改写 Skill 评估 | 立项中（阶段1） | `team/deliverables/hot-skill/` | 另一个agent | | **PROJECT-002** | 众神卡牌（Divine Poker）| 进行中 | `team/deliverables/game-ai/` | 我 | | **PROJECT-003** | 神卡AI插画生成 | 阻塞中（待API配置）| `team/deliverables/game-ai/dev/` | 我 | | **PROJECT-004** | AI剧情AVG（仿真人）| 立项中 | `team/projects/PROJECT-004-ai-avg/`（待创建）| 我 | ### 根本原因 **上下文压缩（compaction）导致记忆丢失**。早期对话（2026-05-11）关于热文项目的细节已经丢失，只剩下 `team/memory/TEAM.md` 中的一条记录。 ### 待办 - [ ] 更新 `team/PROJECT-REGISTRY.md`（改为正确编号）

## Promoted From Short-Term Memory (2026-05-26)

- ### 仍可能出错的情况（概率极低） 1. 我忘记读文件就回答 (<1%) 2. 文件本身写错了 (<1%) 3. 压缩摘要误导我 (<5%) 4. 用户忘了更新文件 ### 我的承诺 - ✅ 涉及项目时，回答前必读 `PROJECT-REGISTRY.md` - ✅ 用户纠正时，立即读文件验证，不争辩 - ✅ 重要信息写入多个文件（冗余存储） --- ## 🚨 关键待办（仍未完成） **`team/PROJECT-REGISTRY.md` 仍然是错误的！** 之前 memory flush 期间无法修改其他文件，需要在新 session 中立即更正： 正确编号： - **PROJECT-001** = 热文采集改写 Skill 评估（另一个agent） - **PROJECT-002** = 众神卡牌（Divine Poker） - **PROJECT-003** = 神卡AI插画生成 - **PROJECT-004** = AI剧情AVG（仿真人） 同时 `memory/2026-05-14.md` 的早期部分也有错误（写的是"PROJECT-001 = 众神卡牌"），但那是历史记录，保留作为错误证据。 --- ## 2026-06-02：PROJECT-001 产品定位讨论纪要

**核心结论**：
- ✅ **定位纠正**：不是单纯"文章改写工具"，而是**热文采集 + 定期采集 + AI改写 一站式平台**
- ✅ **定价策略**：个人版 ¥29/月（初期渗透，后期可涨），团队版 ¥199/月，企业版 ¥499/月
- ✅ **冷启动预算**：¥1000（上线后启用），ToC ¥600 + ToB ¥400 双轨推广
- ✅ **下一步功能（P0）**：多平台一键发布（需 CTO 评估技术可行性）
- ✅ **每周竞品分析**：已设置 cron（每周一 10:00，COO 执行）

**文件归档**：
- 讨论纪要：`team/reports/PROJECT-001-positioning-discussion-2026-06-02.md`
- COO 优化策略 v2：`team/reports/PROJECT-001-commercial-strategy-v2.md`
- PM 定位重评估：`team/reports/PROJECT-001-reposition-report-v2.md`

**项目状态**：
- PROJECT-001 热文采集改写 = 🚀 进行中（新定位）
- PROJECT-002 MoneyPrinterTurbo SaaS = 🚀 进行中（工具型）
- PROJECT-006 众神卡牌 = ❌ 已取消（2026-06-02）

---

## 2026-06-03：PROJECT-002 共享认证模块复用方案

### 002 已有完整认证模块 ✅
```
shared/auth/
├── jwt_handler.py      # JWT 生成/验证（HS256，7天 access + 30天 refresh）
├── auth_middleware.py  # FastAPI 依赖注入式鉴权
├── auth_routes.py      # 注册/登录/刷新/查询
└── models.py           # Pydantic 数据模型
```

### 复用方案：提取为 `team/shared/auth/`
- **可直接复用**：jwt_handler.py、auth_middleware.py、models.py（修改配置导入）
- **需要适配**：auth_routes.py（数据库连接适配 SQLite/PostgreSQL）
- **配置管理**：新增 config.py，各项目通过环境变量/配置文件覆盖

### 关键决策
| 维度 | 决策 |
|------|------|
| JWT_SECRET | 统一（简化用户体验）|
| 用户数据库 | 统一 PostgreSQL user_db（002 已有）|
| 复用方式 | 提取到 team/shared/auth/，各项目 copy + 配置 |

### 下一步
- [ ] 提取 shared/auth/ 到独立目录 ✅ 已完成
- [ ] 新增 config.py 配置管理 ✅ 已完成
- [ ] 001/003 集成认证模块 ✅ 003 已集成并测试通过
- [ ] 001 集成认证模块（待执行）

### 2026-06-03 22:58：003 认证流程测试通过
- 用户注册 `/api/auth/register` ✅
- 用户登录 `/api/auth/login` ✅
- 获取当前用户 `/api/auth/me` ✅
- 受保护 API `/api/accounts` ✅（修复 header 读取方式后）
- 账号管理 CRUD ✅
- JWT Token 有效期 7 天，Refresh Token 30 天

---

## 2026-06-03：PROJECT-003 账号持久化 + 微信公众号正式发布

### 账号持久化存储 ✅
- **模块**: `src/multi_publish/account_store.py`
- **存储**: JSON 文件（`data/accounts.json`）
- **加密**: PBKDF2-HMAC-SHA256（480000 次迭代）+ AES-256
- **特性**: 原子写入、重启自动加载、主密码固定密钥
- **API**: GET/POST/PATCH/DELETE `/api/accounts` + `/validate`

### 微信公众号正式发布 ✅
- **接口**: `cgi-bin/publish`（需要企业认证公众号）
- **流程**: 创建草稿 → 正式发布
- **权限检测**: 自动识别 `invalid permission` 错误
- **fallback**: 正式发布失败返回草稿信息
- **验证**: `validate()` 方法测试认证状态

### 文件变更
| 文件 | 变更 |
|------|------|
| `account_store.py` | 新建（6.3KB）|
| `__init__.py` | 导出 AccountStore，版本 0.1.1 |
| `wechat_mp.py` | 新增 `_publish_draft()` + `validate()` |
| `server.py` | 重写账号 API，集成持久化 |
| `accounts.html` | CRUD + 验证 + 启用/禁用 |
| `config.yaml` | 设置默认 master_password |

---

## Promoted From Short-Term Memory (2026-05-29)

- | 项目 | 状态 | 说明 | |------|------|------| | 仪表盘统计 bug | ⚠️ 待修复 | 遍历字符串列表时统计为 0 | | YouTube 内容不完整 | ⚠️ 待确认 | 字幕提取已实现，需验证 |
- 接续昨天的 scheduler 前端交互完善工作。补丁脚本 `patch_scheduler_frontend.py` 虽打印「第 4 步成功」，但 `httpx` 验证发现 `connectWS` 仍在文件中，需手动清理。
- 写 `fix_websocket.py` 用正则精准清除：

## Promoted From Short-Term Memory (2026-05-29)

- | 检查项 | 结果 | |--------|------| | `function pollJob` 存在 | ✅ | | `function initPolling` 存在 | ✅ |
- | `connectWS` 已删除 | ✅ | | `let ws;` 已删除 | ✅ | | 文件末尾结构正确 | ✅ |

## Promoted From Short-Term Memory (2026-05-30)

- **时间**: 下午/晚上
- **项目路径**: `C:\Users\邱领\.qclaw\workspace\content-aggregator\`
- YouTube 采集失败，错误信息：
- collect failed: All connection attempts failed success=False, collected=0, data_len=0

## 用户身份与偏好

- Python 3.12.10 安装在 C:\Users\邱领\AppData\Local\Programs\Python\Python312
- AI 回复简洁直接，不要废话
- 偏好绿色版/免安装版软件，习惯自行解压部署
- 喜欢浅色系背景

## 经验与决策

- 禁止在报告中虚构角色或职责

## Promoted From Short-Term Memory (2026-05-31)

- 代理配置双端口：7890 和 12334，换着用

## Promoted From Short-Term Memory (2026-06-02)

- Cron任务触发：GBrain安全网每小时记忆扫描

## Promoted From Short-Term Memory (2026-06-03)

- **Bug 1: process_all_sources dead code**
- **Bug 2: process_source double filtering**
- **Other fixes:**

## Promoted From Short-Term Memory (2026-06-04)

- **执行步骤：**

## Promoted From Short-Term Memory (2026-06-06)

- **Error Message**:
- web.server:run_task:510 - 采集失败: name 'logger' is not defined
- **Affected Endpoints**:
- **Root Cause**: Multiple files use `logger` but don't import it

## Promoted From Short-Term Memory (2026-06-07)

- 用户报告 PROJECT-002（MPT SaaS）的 FastAPI 后端认证失败，Streamlit 前端无法登录。
- 创建 `debug_auth_complete.py` 进行端到端测试，发现：
- **结论**：认证系统本身没有问题，JWT_SECRET 一致，Token 格式正确。

## Promoted From Short-Term Memory (2026-06-08)

- 运行 `check_routes.py` 检查 FastAPI 挂载的路由，发现：
- 完成了 feature/llm-client → main 的合并全流程。

## Promoted From Short-Term Memory (2026-06-09)

- 用户问"改写处理器未对接新模型"，经实际测试：

## Promoted From Short-Term Memory (2026-06-13)

- 用户选择 **方案1：应用 frontend-design Skill** 来重设计 PROJECT-001 前端。
- `frontend-design` SKILL.md（位于 D:\Program Files\QClaw\v0.2.24.540\resources\openclaw\config\skills\frontend-design\SKILL.md）
- **「信息实验室」(Information Laboratory)**

## Promoted From Short-Term Memory (2026-06-16)

- **问题**：用户反馈 YouTube 采集的内容改写后仍是英文。

## Promoted From Short-Term Memory (2026-06-16)

- **根因分析**：
- **修复方案**： 修改 `src/content_aggregator/workflows/pipeline.py`：
- ```python detector = LanguageDetector(self.llm_config) lang_result = await detector.detect(content.content, title=content.title)
