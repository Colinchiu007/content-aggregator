# 功能 17 PRD 输出记录

**时间**：2026-06-08
**执行角色**：QClaw (senior-pm skill)
**关联文档**：`PRD-v1.4.0-2026-06-08.md`

## 需求来源

用户（2026-06-08）提出的需求：采集的非中文内容先用 LLM 翻译成中文，再改写，文章详情页展示改写后视图。

## 代码审查发现

1. **Translator** (`processors/translator.py`)：现有翻译器方向为中文→外文，方向相反
2. **Rewriter** (`processors/rewrite/rewriter.py`)：已有 `RewriteConfig.translate_to` 参数，设为 `"zh"` 时可在改写 prompt 中插入翻译指令，但写死为「原文是英文」
3. **Pipeline** (`workflows/pipeline.py`)：`process_all_sources` 和 `process_contents` 中有独立的 translate 步骤，但方向为中文→外文
4. **Article detail page** (`web/templates/article_detail.html`)：已有左右对照的原文/改写后视图，改写按钮区已有「英文先翻译」复选框

## 输出内容

PRD 功能 17 包含 7 个子章节：
- 需求快照（战术级，核心指标）
- 业务逻辑（角色、用例、状态机）
- 功能详情（语言检测模块、翻译扩展、Pipeline集成、元数据、详情页展示、边界条件）
- 数据与埋点
- 技术约束
- 验收标准 (GWT)
- 风险评估

## 关键设计决策

- **翻译+改写合并为一次 LLM 调用**（不拆分两次调用），利用现有 `translate_to="zh"` 机制
- **语言检测优先用规则（CJK字符占比）+ LLM 兜底**，避免误判
- **P1 优先级**，预估 6h
- 版本从 v1.3.0 → v1.4.0

## 文件变更

| 文件 | 变更 |
|------|------|
| `PRD-v1.3.0-2026-06-07.md` → `PRD-v1.4.0-2026-06-08.md` | 重命名 + 内容更新 |