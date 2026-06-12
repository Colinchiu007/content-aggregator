# 修复报告：数据源配置保存无效（2026-06-07）

## 问题描述

用户报告：在数据源配置页面修改 YouTube 频道 ID（删除现有频道），点击"保存配置"后显示"保存成功"，但修改并未生效。

## 根本原因

### Bug 1：前端未传递 Authorization header（401 错误）

**文件**：`web/templates/settings.html`（第 307 行）

**问题**：`saveSettings()` 函数使用原生 `fetch()` 调用 `PUT /api/config`，未注入认证 Token，导致后端返回 401 Unauthorized。

**原代码**：
```javascript
const resp = await fetch('/api/config', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},  // ❌ 缺少 Authorization
    body: JSON.stringify(cfg)
});
```

**修复**：改用 `base.html` 中已定义的 `authFetch()`（自动注入 token）
```javascript
const resp = await authFetch('/api/config', {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(cfg)
});
```

---

### Bug 2：后端条件判断错误，空列表被跳过

**文件**：`web/server.py`（第 1744 行）

**问题**：当用户清空 YouTube 频道（前端发送 `channels: []`），后端条件判断 `fv not in ([], "")` 导致空列表 `[]` 被跳过，配置未更新。

**原代码**：
```python
if isinstance(value, dict) and isinstance(CONFIG["sources"].get(key), dict):
    for fk, fv in value.items():
        if fv is not None and fv not in ([], ""):  # ❌ Bug!
            CONFIG["sources"][key][fk] = fv
```

**原因**：`[] in ([], "")` 返回 `True`（因为 `[] == []`），导致 `fv = []` 时条件为 `False`，更新被跳过。

**修复**：
```python
if isinstance(value, dict) and isinstance(CONFIG["sources"].get(key), dict):
    # 深度合并：只跳过 null（保留前端未传递的字段）
    # 注意：空列表 [] 和空字符串 "" 需要保存（用户主动清空）
    for fk, fv in value.items():
        if fv is not None:  # ✅ 修复：允许空列表和空字符串
            CONFIG["sources"][key][fk] = fv
```

---

## 修复步骤

1. **修复前端**（`settings.html`）：
   - 将 `fetch()` 改为 `authFetch()`，自动注入 token

2. **修复后端**（`server.py`）：
   - 修改条件判断，允许空列表 `[]` 和空字符串 `""` 通过

3. **重启服务**：
   - 杀掉旧进程（占用 8080 端口）
   - 启动新服务

4. **验证测试**：
   - 登录成功 ✅
   - 获取当前配置（channels = `['UCtest1', 'UCtest2']`）✅
   - 清空 channels 并保存 ✅
   - 再次获取配置（channels = `[]`）✅
   - 检查 `config.yaml`（`channels: []`）✅

---

## 验证结果

**测试脚本**：`test_clear_youtube.py`

**输出**：
```
[1] 登录...
  [OK] 登录成功

[2] 获取当前配置...
  [OK] 当前 YouTube 频道: ['UCtest1', 'UCtest2']

[3] 清空 YouTube 频道...
  [OK] 保存成功: {'success': True}

[4] 验证配置是否已清空...
  [OK] 更新后 YouTube 频道: []

==================================================
[SUCCESS] ✅ 修复生效！YouTube 频道已成功清空
```

**config.yaml 验证**：
```yaml
youtube:
  api_key: enc:Z0FBQUFBQnFK...
  channels: []  ✅ 已正确保存为空列表
  search_queries:
  - AI
  search_order: relevance
  search_limit: 10
```

---

## 结论

两个 bug 均已修复：
1. ✅ 前端正确传递 Authorization header（不再报 401）
2. ✅ 后端正确处理空列表（不再跳过 `channels: []`）

用户现在可以正常清空并保存 YouTube 频道配置了。

---

**修复时间**：2026-06-07 17:00  
**修复人**：QClaw (CEO)  
**验证人**：colinchiu
