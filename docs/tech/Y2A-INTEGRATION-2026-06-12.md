# Y2A-Auto 技术整合文档

> **日期**: 2026-06-12  
> **来源项目**: [github.com/fqscfqj/Y2A-Auto](https://github.com/fqscfqj/Y2A-Auto)  
> **整合范围**: P0（LLM 响应处理）+ P1（YouTube 错误诊断）  

---

## 一、背景

Y2A-Auto 是一个 YouTube → AcFun/bilibili 自动化搬运工具，其核心代码经生产环境验证，包含大量健壮的 LLM 响应处理逻辑和 YouTube 错误诊断机制。

Content-Aggregator 存在两个反复出现的痛点：

1. **LLM 推理输出污染改写结果** — 推理模型（sensenova-6.7-flash-lite）频繁输出 Chain-of-Thought
2. **YouTube 错误信息不明确** — 用户无法区分配额耗尽、Key 无效、限速等场景

本整合从 Y2A-Auto 移植经生产验证的解决方案，覆盖 P0 + P1 优先级。

---

## 二、移植文件清单

### 2.1 新增文件

| 文件 | 行数 | 来源 | 功能 |
|------|------|------|------|
| `src/content_aggregator/clients/llm_utils.py` | ~360 行 | Y2A-Auto `modules/utils.py` + `modules/ai_enhancer.py` | LLM 响应处理工具集 |

### 2.2 修改文件

| 文件 | 变更说明 |
|------|----------|
| `src/content_aggregator/clients/llm_client.py` | 集成 thinking disabled 控制 + 简化响应处理 |
| `src/content_aggregator/processors/rewrite/rewriter.py` | 输入预清洗 + 推理标签清理升级 |
| `src/content_aggregator/processors/language_detector.py` | 使用 `extract_json_from_text()` 提升解析健壮性 |
| `src/content_aggregator/sources/youtube.py` | 错误分级诊断（`_classify_api_error()`） |

---

## 三、核心模块详解：llm_utils.py

### 3.1 函数地图

```
llm_utils.py
├── 推理内容剥离
│   ├── strip_reasoning_thoughts()    # 移除 <think>/```think 标签
│   └── strip_code_fences()           # 移除 ```lang 代码块围栏
│
├── JSON 提取
│   ├── _extract_balanced_json_block() # 括号平衡提取（内部函数）
│   ├── extract_json_from_text()       # 从任意文本提取 JSON
│   ├── get_chat_message_text()        # 提取 message 纯文本
│   └── extract_chat_message_json()    # 优先 parsed，回退文本提取
│
├── 输入内容预清洗
│   ├── clean_input_content()          # 主入口：去 URL/推广/CTA
│   ├── _normalize_whitespace()        # 规范化空白
│   └── _looks_like_promo_line()       # 推广行检测
│
├── 思考模式控制
│   └── build_thinking_disabled_body() # 在请求体加 thinking: disabled
│
└── YouTube 错误诊断
    ├── looks_like_youtube_bot_challenge()
    ├── looks_like_format_selection_error()
    └── summarize_yt_error()
```

### 3.2 关键函数设计

#### `strip_reasoning_thoughts(text)`

兼容两种推理格式：
- DeepSeek 风格: `<think>...</think>` (大小写/跨行)
- 代码块风格: ```` ```think ... ```  ````

#### `extract_json_from_text(text, expected_type=None)`

多级回退策略：
1. 先用 `strip_reasoning_thoughts` + `strip_code_fences` 预处理
2. 尝试直接 `json.loads()` 解析全文
3. 用 `_extract_balanced_json_block()` 查找括号平衡的 JSON 块
4. 尝试多个候选（全文 + {块 + [块），返回第一个解析成功的

#### `clean_input_content(text, max_blocks=2)`

预处理流水线：
1. 移除所有 URL（http/https/ftp/www）
2. 移除邮箱、社交账号（@mention）、标签（#hashtag）
3. 移除赞助链接（Patreon/Ko-fi/BuyMeACoffee）
4. 移除 CTA 短语（"link in description"等）
5. 按段检测推广密度，超过 50% 行是推广的段落整段跳过
6. 段内逐行过滤 CTA/互动文本

### 3.3 三层推理防御架构

```
请求发送前 ─── build_thinking_disabled_body()
    ├── 添加 extra_body.thinking = {type: "disabled", enabled: false}
    └── 仅对有推理能力的模型尝试（通过 has_thinking_param 检测）
         ↓
API 返回 ─── strip_reasoning_thoughts() + _is_reasoning_content()
    ├── 先剥离 <think> 标签
    ├── 检测是否是推理内容（英文开头、比例异常等）
    └── 是 → 从 reasoning 字段提取最终答案
         ↓
API 报错 ─── 自动降级重试
    ├── 检测 "unknown parameter" / "unsupported" 等信号
    └── 移除 extra_body 参数，重新发送请求
```

---

## 四、YouTube 错误诊断

### 4.1 错误分类表

| HTTP 状态码 | 特征检测 | 用户提示 |
|-------------|----------|----------|
| 400 + keyInvalid | `"keyInvalid"` in response | YouTube API Key 无效，请检查 .env 中的 YOUTUBE_API_KEY |
| 400 + badRequest | `"badRequest"` in response | 请求参数错误 |
| 403 + bot_challenge | 检测 `"Sign in to confirm"` / `"not a bot"` / `"HTTP Error 403"` 等 | 可能被反机器人机制拦截。尝试: 1) 启用代理 2) 更换 API Key 3) 稍后再试 |
| 403 + quotaExceeded | `"quotaExceeded"` in response | YouTube API 配额已耗尽，请稍后再试（第二天配额刷新） |
| 404 | - | YouTube 频道/视频不存在或已删除 |
| 429 | - | YouTube API 速率限制，请降低采集频率 |
| 5xx | - | YouTube 服务端错误，可能为临时问题 |

### 4.2 Bot 挑战检测

移植自 Y2A-Auto `modules/youtube_handler.py`，检测以下信号：
- `"Sign in to confirm"` — YouTube 要求登录验证
- `"not a bot"` — reCAPTCHA/bot 验证页面
- `"Signature extraction failed"` — 签名提取失败
- `"Some formats may be missing"` — 部分格式缺失
- `"HTTP Error 403"` / `"decodeURIComponent"` — 播放器安全校验

---

## 五、对原有代码的改动说明

### 5.1 llm_client.py

**移除**: `_is_reasoning_content()` 和 `_extract_final_from_reasoning()` 已简化，委托给 `llm_utils.py`  
**新增**: 
- `has_thinking_param` 检测 — 仅推理模型添加 `extra_body`  
- `build_thinking_disabled_body()` 调用  
- `has_retried_without_thinking` 降级标志  
- 响应处理简化 — 使用 `strip_reasoning_thoughts()` 替代手工正则  

### 5.2 rewriter.py

**新增 import**: `clean_input_content`, `extract_json_from_text`, `strip_reasoning_thoughts`  
**`_build_prompt()`** — 在获取 content.title/content.content 后立即调用 `clean_input_content()`  
**`_parse_response()`** — 用 `strip_reasoning_thoughts()` 替代手工 `<think>` 正则  

### 5.3 language_detector.py

**`_parse_llm_response()`** — 重写为使用 `extract_json_from_text()`，处理：
- `<think>...</think>` 包裹
- ` ```json ... ``` ` 代码块 
- 文本中任意位置的 JSON 提取

### 5.4 youtube.py

**新增**:
- `_classify_api_error()` — 400/403/404/429/5xx 分级诊断
- 所有 `resp.raise_for_status()` → 替换为 `_classify_api_error()` 调用
- `connect()` — 增加 Bot 挑战/配额耗尽检测

---

## 六、测试建议

### 6.1 LLM 响应处理

```python
# 测试推理标签剥离
assert strip_reasoning_thoughts("Some <think>internal analysis</think>answer") == "answer"
assert strip_reasoning_thoughts("```think\nstep by step\n```final") == "final"

# 测试 JSON 提取
assert extract_json_from_text("```json\n{\"a\": 1}\n```") == {"a": 1}
assert extract_json_from_text("Answer: {\"b\": 2}") == {"b": 2}

# 测试内容清洗
cleaned = clean_input_content("Subscribe to my channel at https://youtube.com/@xxx\nActual content here")
assert "Subscribe" not in cleaned
assert "Actual content here" in cleaned
```

### 6.2 YouTube 错误诊断

```python
assert looks_like_youtube_bot_challenge("Sign in to confirm you're not a bot")
assert not looks_like_youtube_bot_challenge("正常错误信息")
assert "配额" in _classify_api_error(403, "quotaExceeded")
```

---

## 七、Y2A-Auto 剩余可复用点（非 P0/P1）

| 优先级 | 功能 | 来源文件 | 建议 |
|--------|------|----------|------|
| P2 | 任务断点续跑 (checkpoint) | `task_manager.py` | 当前 scheduler 缺乏持久化 |
| P2 | VTT→SRT 转换引擎 | `utils.py` `_convert_vtt_text_to_srt_text()` | 字幕格式转换 |
| P2 | 翻译质量检测 (QC) | `subtitle_translator.py` | 批量翻译后残留检测 |
| P3 | VAD 处理器 + 分片 ASR | `vad_processor.py` + `speech_recognition.py` | 本地语音识别 |
| P3 | 内存感知调度 | `task_manager.py` | 并发控制 |
| P2 | 任务断点续跑 (checkpoint) | `task_manager.py` | ✅ 已完成 (see §八) |
| P2 | VTT→SRT 转换引擎 | `utils.py` `_convert_vtt_text_to_srt_text()` | 字幕格式转换 |
| P2 | 翻译质量检测 (QC) | `subtitle_translator.py` | 批量翻译后残留检测 |
| P3 | VAD 处理器 + 分片 ASR | `vad_processor.py` + `speech_recognition.py` | 本地语音识别 |
| P3 | 内存感知调度 | `task_manager.py` | 并发控制 (已有基本实现) |
| P3 | CookieCloud 集成 | `cookiecloud.py` | ✅ 已完成 (see §九) |

---

## 八、断点续跑系统详解（P2 已完成）

### 8.1 架构

```
┌─────────────────────────────────────────────────────┐
│                   pipeline.py                        │
│  process_contents() ──→ 每通过一阶段写 checkpoint    │
│  process_with_checkpoint() ──→ 创建 task + 包装     │
│  process_all_sources_with_checkpoint()              │
│  recover_interrupted_tasks()                        │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                 task_store.py                        │
│  SQLite (WAL)                                       │
│  ├─ tasks (任务)                                    │
│  ├─ items (内容项 + stage)                          │
│  └─ checkpoint_log (阶段日志)                       │
│                                                      │
│  Thread-safe: 全方法使用独立连接 + PRAGMA 配置      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│                  scheduler.py                        │
│  init_checkpoint_store() ──→ 存储初始化              │
│  start() ──→ 启动时检测中断任务                      │
│  cancel_task() ──→ 线程安全取消                      │
│  load_from_config() ──→ 使用 checkpoint 包装器       │
└─────────────────────────────────────────────────────┘
```

### 8.2 流水线阶段（ItemStage）

| 阶段 | 含义 | 恢复策略 |
|------|------|----------|
| `collected` | 原始数据已采集 | 走完整 pipeline |
| `filtered` | 已通过敏感词+去重 | 从改写开始 |
| `rewriting` | LLM 改写中 | ⚠️ 回退到 rewritten 之前 |
| `rewritten` | 改写结果已保存 | 直接从 processed_data 读取 |
| `completed` | 已转为 Article | ✅ 跳过（不再处理）|
| `failed` | 该 item 处理失败 | ❌ 跳过（标记为失败）|

### 8.3 从 Y2A-Auto 移植的关键模式

| 模式 | Y2A-Auto | Content-Aggregator |
|------|----------|-------------------|
| 任务去重 | `_mark_task_active()` | `mark_task_active()` |
| 取消机制 | `request_task_cancel()` + Event | 同上 |
| 中断恢复 | `recover_interrupted_tasks_to_pending()` | `recover_interrupted_tasks()` → 只记录，不做自动恢复 |
| 内存感知 | `_get_memory_usage_percent()` | `should_reduce_concurrency()` |
| Pipeline Checkpoint | `pipeline_checkpoint` 字段 + 阶段常量 | items 表 stage 字段 + ItemStage 枚举 |
| SQLite 连接池 | 全局 DB 连接 + PRAGMA | 每次方法调用创建+关闭连接 |

### 8.4 与 Y2A-Auto 的差异

| 方面 | Y2A-Auto | Content-Aggregator |
|------|----------|-------------------|
| 并发模型 | 线程 (BackgroundScheduler) | asyncio |
| 取消检查 | `_raise_if_cancelled()` (同步) | `is_task_cancelled()` (异步循环) |
| 恢复策略 | 自动恢复 to pending | 仅检测和记录，由 scheduler 决定是否重新执行 |
| DB 连接 | 全局连接 + 重试 | 每次新建连接（asyncio 安全）|
| 阶段粒度 | 8 个 (video pipeline) | 6 个 (content pipeline) |

---

## 九、CookieCloud 集成模块详解（P3 已完成）

### 9.1 文件结构

```
src/content_aggregator/sources/cookiecloud.py  (499 行)
```

### 9.2 核心函数

| 函数 | 从 Y2A-Auto 移植 | 变更 |
|------|----------------|------|
| `validate_settings()` | `validate_cookiecloud_settings()` | 简化，去掉了 app_root 安全检查 |
| `fetch_payload()` | `fetch_cookiecloud_payload()` | 去掉 session 参数，简化超时 |
| `decrypt_payload()` | `decrypt_cookiecloud_payload()` | 去掉 crypto 类型协商逻辑，自动全部尝试 |
| `extract_youtube_cookies()` | `build_youtube_netscape_cookies()` | 名称简化，逻辑不变 |
| `write_cookie_file()` | `_write_cookie_file()` | 公开函数 |
| `sync_youtube_cookies()` | `sync_cookiecloud_to_youtube_file()` | 单体返回，分步异常捕获 |

### 9.3 与 Y2A-Auto 的差异

| 方面 | Y2A-Auto | Content-Aggregator |
|------|----------|-------------------|
| **模块依赖** | 全局 task_manager 引用 | 零耦合独立模块 |
| **路径安全** | `resolve_cookie_output_path()` 严格检测 app root | 简化为项目相对路径 |
| **配置加载** | 全局 settings 字典 | `load_config(config)` 读取器 + config.yaml |
| **错误处理** | `try_cookiecloud_youtube_sync()` 双层返回值 | 单层 `sync_youtube_cookies()` 返回 dict |
| **CLI** | 无 | 内置 `if __name__ == "__main__"` CLI |
| **日志** | 模块级 logger | `logging.getLogger(__name__)` |
| **加密函数** | `_decrypt_*` × 4 + `_decrypt_*_preview_compat` × 4 | `_decrypt_*` × 4（去掉 preview_compat 后缀） |

### 9.4 集成点

当前为纯工具模块，未被任何采集器引用。后续集成方式：

```python
from content_aggregator.sources.cookiecloud import sync_youtube_cookies, load_config

# 在 youtube.py 或其他采集器内部
settings = load_config(config)
if settings:
    result = sync_youtube_cookies(settings)
    if result["success"]:
        # result["output_path"] 包含 cookie 文件路径
        # 可传给 yt-dlp 等工具
```

---

*由 CEO (QClaw) 维护，2026-06-12*
