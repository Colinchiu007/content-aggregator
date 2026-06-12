# 2026-06-05 19:06 - 排版发布按钮报错修复

## 问题
点击文章详情页「排版发布」按钮，控制台报错：
```
Uncaught (in promise) TypeError: Cannot read properties of null (reading 'classList')
    at openWeChatPublish @ article_detail.html:554
```

## 根因
微信排版发布弹窗的 HTML（`<div class="modal-overlay" id="wechatPublishModal">`）位于 `{% block content %}` 的 `{% endblock %}` **之后**、`{% block extra_js %}` **之前**——即两个 block 之间的空白区域。
Jinja2 模板继承机制：只有 `{% block xxx %} ... {% endblock %}` 内的内容会被渲染，block 外的内容全部丢弃。
→ 浏览器收到的 HTML 中**根本没有这个弹窗 DOM 元素** → `getElementById('wechatPublishModal')` 返回 null → 调用 `.classList` 报 TypeError。

## 修复
将弹窗整体（style + div + {% endblock %}）从 block 外移入 `{% block content %}` 内部：
- 删除原 `{% endblock %}`（第 133 行，content block 结束标记）
- 弹窗内容保持在原位（自然落入 content block 内）
- 在弹窗 HTML 结束后、`{% block extra_js %}` 前添加 `{% endblock %}`

## 验证
Python 渲染测试确认：
- `id="wechatPublishModal"` ✅ 存在于渲染输出中
- `openWeChatPublish` 函数 ✅ 能找到 DOM 元素

## 文件变更
- `web/templates/article_detail.html`：移动 `{% endblock %}` 位置，将弹窗纳入 content block

## 经验教训
Jinja2 模板继承中，**所有动态内容必须放在 `{% block %}` 内**。block 外的 HTML 静默丢失，不会报错但也不会渲染。
