# DESIGN-SYSTEM.md — Content Aggregator 前端规范

> **主题**: Cold Modern（冷峻现代）  
> **生效日期**: 2026-06-07  
> **维护者**: PROJECT-001 团队

---

## 📁 CSS 架构

| 文件 | 用途 | 修改规则 |
|------|------|----------|
| `web/static/style.css` | 基础样式（布局、通用组件） | ❌ **禁止修改**（会影响全局） |
| `web/static/style-cold-modern.css` | 冷峻现代主题（CSS 变量覆盖） | ✅ 允许修改（仅变量覆盖） |
| `web/static/style-pages.css` | 页面级样式（新增页面必须添加） | ✅ **优先修改**（新增样式写这里） |

### 加载顺序（`base.html`）
```html
<link href="/static/style.css" rel="stylesheet">
<link href="/static/style-cold-modern.css" rel="stylesheet">  <!-- 覆盖变量 -->
<link href="/static/style-pages.css" rel="stylesheet">  <!-- 页面级样式 -->
```

---

## ❌ 禁止事项

### 1. 禁止写 inline styles
```html
<!-- ❌ 错误 -->
<div style="padding:20px; background:#fff;">

<!-- ✅ 正确 -->
<div class="card">
```

### 2. 禁止直接修改 `style.css`
- 这是全局基础样式，修改会影响所有页面
- 需要覆盖样式 → 在 `style-pages.css` 中添加更高优先级的选择器

### 3. 禁止创建新的 CSS 文件
- 所有新增样式必须写在 `style-pages.css`
- 如果文件过大（>50KB），才考虑拆分

---

## ✅ 必须事项

### 1. 新增页面必须引用 `style-pages.css`
```html
<!-- 在 base.html 中已全局引用，无需额外操作 -->
<!-- 如果是独立 HTML 文件，需手动添加： -->
<link href="/static/style-pages.css" rel="stylesheet">
```

### 2. 样式必须用 CSS 类
可用的基础类（定义在 `style-pages.css`）：
- **布局**: `.page-header`, `.settings-layout`, `.compare-container`
- **卡片**: `.card`, `.card-header`, `.card-body`
- **按钮**: `.btn`, `.btn-primary`, `.btn-secondary`
- **表单**: `.form-grid`, `.form-group`, `.form-actions`
- **表格**: `.data-table`, `.status-badge`
- **筛选栏**: `.filter-bar`, `.filter-group`
- **文章相关**: `.article-tags`, `.compare-panel`, `.article-detail`

（完整列表参见 `style-pages.css` 第 1-500 行）

### 3. 提交前检查
```bash
# 检查是否有 inline styles
grep -r 'style="' web/templates/

# 如果有输出，说明有 inline styles，必须改为 CSS 类
```

---

## 🎨 设计规范

### 色彩体系（冷峻现代）
```css
--bg-primary: #f8f9fa;      /* 主背景（极淡蓝灰）*/
--bg-card: #ffffff;           /* 卡片背景（纯白）*/
--text-primary: #212529;     /* 主文字（深炭灰）*/
--accent-color: #4a90e2;    /* 强调色（冷蓝）*/
--border-color: #dee2e6;     /* 边框（蓝灰）*/
```

### 字体
- **标题**: IBM Plex Sans
- **正文**: Inter
- **代码/数字**: JetBrains Mono

### 圆角 & 阴影
- **圆角**: 6px（更小更现代）
- **阴影**: `0 2px 8px rgba(0,0,0,0.1)`（微妙阴影）

---

## 🛠️ 新增组件流程

### 步骤 1：在 `style-pages.css` 添加 CSS 类
```css
/* 新增：文章卡片悬停效果 */
.article-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
```

### 步骤 2：在 HTML 中用 `class=""` 引用
```html
<div class="article-card">
    <!-- 内容 -->
</div>
```

### 步骤 3：提交前运行检查
```bash
# 检查是否有 inline styles
git diff --cached | grep 'style="'

# 如果没有输出，说明合规 ✅
```

---

## 🚨 常见问题

### Q1: 我需要覆盖某个组件的样式，怎么办？
**A**: 在 `style-pages.css` 中添加更高优先级的选择器：
```css
/* 错误：直接修改 style.css */
/* 正确：在 style-pages.css 中覆盖 */
.card.article-card {
    padding: 24px;  /* 更高优先级 */
}
```

### Q2: 我需要写动态样式（根据 JS 状态变化），怎么办？
**A**: 用 CSS 类切换，不要用 `element.style.xxx`：
```javascript
// ❌ 错误
document.getElementById('myDiv').style.display = 'none';

// ✅ 正确
document.getElementById('myDiv').classList.add('hidden');
```
（`.hidden` 类定义在 `style-pages.css`）

### Q3: 我发现的 bug 是 `style.css` 导致的，能改吗？
**A**: 可以，但必须：
1. 在 `DESIGN-SYSTEM.md` 中记录修改原因
2. 在 git commit 中详细说明
3. 通知所有团队成员

---

## 📝 更新日志

| 日期 | 修改者 | 修改内容 |
|------|--------|----------|
| 2026-06-07 | CEO (QClaw) | 初始版本，定义 Cold Modern 主题规范 |

---

## 📚 参考文件

- **设计系统**: `web/static/style-cold-modern.css`
- **页面样式**: `web/static/style-pages.css`
- **全局样式**: `web/static/style.css`
- **模板文件**: `web/templates/*.html`

---

**📌 所有开发者（包括 AI Agent）必须遵守本规范。违反规范会导致代码 review 不通过。**
