# 修复记录 - 2026-06-08

## 问题1：YouTube 采集数量限制不生效

**现象**：仪表盘设置每个源采集 1 篇，实际采了 6 篇

**根因**：
- `pipeline.py` 中 `_parse_single_config` 生成 YouTube entry 时，`max_results` 和 `max_items` 用的是 `search_limit`（默认 10）
- `limit_per_source` 虽然在 `process_sources` 中会覆盖 `collect_kwargs['max_results']`，但如果前端没传 `limit` 参数，entry 就用默认值 10

**修复**：
- 修改优先级：`dashboard limit > config search_limit > 默认 20`
- 让 `limit_per_source` 能正确覆盖 `search_limit`

**文件**：`src/content_aggregator/workflows/pipeline.py` (第 928-931 行)

---

## 问题2：页面卡死 + 提示条泛滥

**现象**：采集时右上角弹出多条提示，页面链接暂时无反应，一分钟后恢复正常

**根因**：
- 每个视频完成都推送一条 WebSocket 消息
- 前端每条都弹 toast，DOM 操作过多导致浏览器卡死

**修复**：
- `showToast` 函数加节流防抖：500ms 内相同消息只弹一次

**文件**：`web/templates/base.html` (showToast 函数)

---

## 测试建议

1. 刷新页面测试前端修复（无需重启后端）
2. 重启后端测试数量限制修复：
   ```bash
   cd content-aggregator
   python -m uvicorn web.server:app --reload
   ```
3. 在仪表盘设置每个源采集 1 篇，观察是否只采 1 篇
4. 观察 toast 是否不再泛滥
