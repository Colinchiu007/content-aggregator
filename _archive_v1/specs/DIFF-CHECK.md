# 差异检查清单

> 版本: 1.0.0  
> 最后更新: 2026-05-25  
> 目的: 记录 Spec 与现有代码之间的差异，指导后续修复

---

## 1. 检查方法

### 验证流程
```
1. 阅读 Spec 中的行为描述
2. 检查代码实现是否一致
3. 记录差异（✅ 一致 / ⚠️ 有差异 / ❌ 不一致）
4. 提出修复建议
```

---

## 2. 系统总览差异

### 2.1 数据源支持

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| RSS | `RSSCollector` 存在 | ✅ 一致 |
| YouTube | `YouTubeCollector` 存在 | ✅ 一致 |
| Twitter | `TwitterCollector` 存在 | ✅ 一致 |
| TikTok | `TikTokCollector` 存在 | ✅ 一致 |
| 抖音 | `DouyinCollector` 存在 | ✅ 一致 |
| 小红书 | `XiaohongshuCollector` 存在 | ✅ 一致 |
| 微信公众号 | `WechatCollector` 存在 | ✅ 一致 |
| Sitemap | `SitemapCollector` 存在 | ✅ 一致 |
| 自定义 API | `ApiCollector` 存在 | ✅ 一致 |

**验证结果**: 所有 9 种数据源 Collector 均已实现，位于 `sources/collectors/`

### 2.2 处理流程

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| 采集 → **过滤** → 改写 | Pipeline 已调用过滤模块 | ✅ **已修复（2026-05-25）** |
| simhash 去重 | `DedupFilter` 已实现并集成 | ✅ **已修复** |
| 敏感词过滤 | `SensitiveFilter` 已实现并集成 | ✅ **已修复** |

**验证结果（2026-05-25）**:
1. ✅ `SensitiveFilter` 存在于 `processors/filter/sensitive.py`
2. ✅ `DedupFilter` 存在于 `processors/filter/dedup.py`
3. ✅ `workflows/pipeline.py` 已导入这两个模块
4. ✅ `workflows/pipeline.py` 已调用 `_apply_filters()` 方法
5. ✅ 所有处理流程（process_url, process_all_sources, process_source, process_contents）均已集成过滤
6. ✅ 配置文件 `config/config.example.yaml` 已添加过滤配置
7. ✅ 测试脚本 `scripts/test_filters.py` 已通过全部测试

**结论**: 过滤功能已完整集成到主流程中！

**修复内容**:
1. ✅ 在 `ContentPipeline.__init__()` 中初始化过滤器 `_init_filters()`
2. ✅ 在 `process_url()` 中添加过滤步骤
3. ✅ 在 `process_all_sources()` 中添加过滤步骤
4. ✅ 在 `process_source()` 中添加过滤步骤
5. ✅ 在 `process_contents()` 中添加过滤步骤
6. ✅ 添加 `_apply_filters()` 异步方法协调两个过滤器
7. ✅ 配置文件添加 `filter` 配置节
8. ✅ 编写测试脚本验证过滤功能

---

## 3. 改写处理器差异

### 3.1 提示词优先级

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| custom_prompt 最高优先级 | `_build_prompt` 第一行检查 | ✅ 一致 |
| config.yaml 覆盖默认值 | `self._custom_prompts` 字典 | ✅ 一致 |
| 内置默认值最低优先级 | `DEFAULT_PROMPTS` 字典 | ✅ 一致 |

### 3.2 字数约束

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| 最小 500 字 | `min_word_count=500` | ✅ 一致 |
| 最大 5000 字 | `max_word_count=5000` | ✅ 一致 |
| 目标 3000 字 | `target_word_count=3000` | ✅ 一致 |

### 3.3 重试策略

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| 重试 3 次 | `retry = self.llm_config.get("retry", 3)` | ✅ 一致 |
| 指数退避 | `wait_time = 2 ** attempt` | ✅ 一致 |
| 429 触发重试 | 检查 status_code == 429 | ✅ 一致 |

### 3.4 响应解析

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| 清理寒暄前缀 | `_prefix_patterns` 正则列表 | ✅ 一致 |
| 提取标题 | 正则匹配【标题】 | ✅ 一致 |
| 默认截取 200 字摘要 | `_truncate(summary, 200)` | ✅ 一致 |

---

## 4. Pipeline 差异

### 4.1 并发控制

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| 默认 3 并发 | `Semaphore(3)` | ✅ 一致 |
| 批量改写使用信号量 | `rewrite_batch` 中使用 | ✅ 一致 |

### 4.2 错误处理

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| 采集失败不中断流程 | try-except + continue | ✅ 一致 |
| 改写失败 fallback 原文 | `Article.from_content(content)` | ✅ 一致 |

### 4.3 数据源解析

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| RSS 过滤 enabled=false | `_parse_rss_sources` 中检查 | ✅ 一致 |
| max_items → max_results 映射 | `_parse_single_config` 中转换 | ✅ 一致 |

---

## 5. Web API 差异

### 5.1 端点存在性

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| GET `/` | 存在 | ✅ 一致 |
| GET `/articles` | 存在 | ✅ 一致 |
| GET `/sources` | 存在 | ✅ 一致 |
| POST `/api/collect` | ⚠️ 待验证 | ⚠️ |
| POST `/api/rewrite` | ⚠️ 待验证 | ⚠️ |

### 5.2 响应格式

| Spec 声明 | 代码实际情况 | 状态 |
|-----------|--------------|------|
| success 字段 | 检查 FastAPI 路由 | ⚠️ 待验证 |
| error 字段 | 检查 FastAPI 路由 | ⚠️ 待验证 |

---

## 6. 待修复项汇总

### ✅ 已修复（2026-05-25）

| # | 问题 | 修复状态 |
|---|------|----------|
| 1 | 敏感词过滤逻辑缺失 | ✅ 已集成到 Pipeline |
| 2 | 去重过滤逻辑缺失 | ✅ 已集成到 Pipeline |

### 🟡 中优先级

| # | 问题 | 影响 | 修复建议 |
|---|------|------|----------|
| 3 | 多个数据源未实现 | Spec 声明与实际不符 | 标注为"计划支持"或移除 |
| 4 | Web API 端点未验证 | 不确定是否已实现 | 补充代码检查 | ✅ 已验证（2026-05-28） |

### 🟢 低优先级

| # | 问题 | 影响 | 修复建议 | 状态 |
|---|------|------|----------|------|
| 5 | SEO Processor 规格缺失 | 开发无指导 | 补充 `05-seo-processor.md` | ✅ 已完成（2026-05-27） |
| 6 | 导出格式详细规格缺失 | 输出格式不明确 | 补充 `04-export-formats.md` | ✅ 已完成（2026-05-27） |
| 7 | 存储层规格缺失 | 存储逻辑不明确 | 补充 `07-storage.md` | ✅ 已完成（2026-05-28） |
| 8 | 调度器规格缺失 | 调度逻辑不明确 | 补充 `06-scheduler.md` | ✅ 已完成（2026-05-28） |

---

## 7. 验证清单

### 需要人工验证的项目

- [x] Twitter Collector 是否存在？ ✅
- [x] TikTok Collector 是否存在？ ✅
- [x] 抖音 Collector 是否存在？ ✅
- [x] 小红书 Collector 是否存在？ ✅
- [x] 微信公众号 Collector 是否存在？ ✅
- [x] 敏感词过滤是否已实现？ ✅
- [x] 去重过滤是否已实现？ ✅
- [x] 过滤功能是否已集成到 Pipeline？ ✅

### 需要代码检查的项目

- [x] Web API 规格是否已与实际代码一致？ ✅ (2026-05-27 已更新 v1.1.0)
- [x] `04-export-formats.md` 是否已补充？ ✅ (2026-05-27)
- [x] `05-seo-processor.md` 是否已补充？ ✅ (2026-05-27)
- [x] `07-storage.md` 是否已补充？ ✅ (2026-05-28)
- [x] Web UI 一致性检查？ ✅ (2026-05-28) 所有 API 端点与模板调用匹配
- [x] `06-scheduler.md` 是否已补充？ ✅ (2026-05-28)

---

## 8. 更新日志

| 日期 | 变更 |
|------|------|
| 2026-05-25 | 初始版本，反向工程自 v0.1.0 代码 |
| 2026-05-25 | ✅ 修复高优先级问题：敏感词过滤和去重过滤已完整集成到 Pipeline |
| 2026-05-27 | ✅ 更新 Web API 规格（v1.1.0）与实际代码一致（异步任务模式） |
| 2026-05-27 | ✅ 补充导出格式详细规格（`04-export-formats.md`） |
| 2026-05-27 | ✅ 补充 SEO Processor 规格（`05-seo-processor.md`） |
| 2026-05-27 | ✅ 补充 YouTube/Twitter 数据源规格 |
| 2026-05-28 | ✅ Web UI 一致性检查通过（所有端点匹配） |
| 2026-05-28 | ✅ 补充存储层规格（`07-storage.md`） |
| 2026-05-28 | ✅ 补充定时调度规格（`06-scheduler.md`） |

---

## 下一步行动

1. **执行验证清单** - 逐项检查上述待验证项目
2. **更新差异状态** - 根据检查结果更新本文档
3. **修复高优先级问题** - 先修复代码，再更新 Spec
4. **补充缺失的 Spec** - 按优先级补充详细规格
