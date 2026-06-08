# 样式预览问题排查报告

## 问题描述
用户反馈"继续测试之前的样式预览"，说明预览区域仍有问题。

## 代码检查
✅ `loadPreview()` 函数（第 327-337 行）已在用 `apiPost()`
✅ `apiPost()` 函数（第 351-354 行）正确实现
✅ `authFetch()` 函数（第 333-349 行）正确注入 Token

## 可能原因

### 1. 浏览器缓存（最可能）
旧版本的 `article_detail.html` 还在用 `fetch()`（没有 Token），导致 401 认证失败。

**解决方法**：
- 按 `Ctrl + F5` 强制刷新（清除缓存）
- 或者在开发者工具 `Network` 标签勾选 `Disable cache`，然后刷新页面

### 2. Token 过期或不存在
`localStorage` 里没有 `auth_token`，导致 `getAuthHeaders()` 返回空对象。

**检查方法**（在 Console 执行）：
```javascript
localStorage.getItem('auth_token')
```
- 如果返回 `null` → 未登录，需要先登录
- 如果返回字符串（如 `eyJ...`）→ Token 存在，问题在别处

### 3. 预览区域元素 ID 不对
`preview-area` 元素可能不存在，导致 `area.innerHTML = result.html` 失败。

**检查方法**（在 Console 执行）：
```javascript
document.getElementById('preview-area')
```
- 如果返回 `null` → 元素不存在，需要检查 HTML 结构
- 如果返回元素 → 元素存在，问题在别处

### 4. JavaScript 错误阻止了渲染
`loadPreview()` 里有 JavaScript 错误，导致 `area.innerHTML = result.html` 没执行。

**检查方法**：
- 按 F12 → Console 标签，看有没有红色报错

## 排查步骤（用户需执行）

**步骤1**: 按 `Ctrl + F5` 强制刷新（清除缓存）

**步骤2**: 按 F12 → Console 标签，执行：
```javascript
localStorage.getItem('auth_token')
```
- 如果返回 `null` → 先登录，再测试
- 如果返回字符串 → 继续执行下一步

**步骤3**: 按 F12 → Console 标签，执行：
```javascript
document.getElementById('preview-area')
```
- 如果返回 `null` → 把 `article_detail.html` 的 HTML 结构发给我
- 如果返回元素 → 继续执行下一步

**步骤4**: 按 F12 → Console 标签，执行：
```javascript
loadPreview()
```
- 看 Console 有没有报错
- 看 Network 标签有没有 `preview` 请求（Status 是否是 200）

**步骤5**: 如果 `preview` 请求返回 200，看 Response 是否包含 `style="..."`（确认后端返回正确）

**步骤6**: 如果后端返回正确，看预览区域是否显示样式（右键"检查"→ 看 `preview-area` 元素的 `innerHTML` 是否包含 `style="..."`）

## 待确认
- [ ] 用户是否已按 `Ctrl + F5` 强制刷新
- [ ] `localStorage.getItem('auth_token')` 是否返回字符串（非 `null`）
- [ ] `document.getElementById('preview-area')` 是否返回元素（非 `null`）
- [ ] `loadPreview()` 执行时有没有 JavaScript 错误
- [ ] `/api/wechat/preview/{id}` 请求是否返回 200
- [ ] 后端返回的 `html` 字段是否包含 `style="..."`（确认后端返回正确）
- [ ] 预览区域的 `innerHTML` 是否包含 `style="..."`（确认前端正确插入）

## 下一步
1. 等待用户执行排查步骤，并发送 Console 错误、Network 请求详情
2. 根据错误信息，修复前端问题
3. 如果所有排查步骤都正确，但预览仍无样式，检查 CSS 是否被覆盖（开发者工具 → Elements → 看 `preview-area` 元素的 `style` 属性是否被划掉）

---

**创建时间**: 2026-06-06 16:37
**创建人**: AI Assistant
**状态**: 待用户排查
