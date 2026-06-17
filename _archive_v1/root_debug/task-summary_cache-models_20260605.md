# 2026-06-05 18:58 - 文章详情页 JS 错误修复 + 模型切换

## 问题
用户打开文章详情页时，点击"排版发布"按钮无响应，控制台报 `Uncaught SyntaxError: Invalid Unicode escape sequence`。

## 排查过程
1. **JS 编码问题**：第一次认为是 `tojson` 过滤器将中文 `{{ article.title | tojson }}` 渲染为 `\uXXXX` 转义序列，浏览器无法解析。**修复**：改为从 DOM 读取 `document.querySelector('h1')?.dataset?.articleId`。
2. **第二次错误**：出现 `Cannot read properties of null (reading 'split')`。**修复**：从 `window.location.pathname.split('/')` 改为 `document.querySelector('h1')?.dataset?.articleId`，并给 `<h1>` 增加 `data-article-id` 属性。
3. **第三次错误**：用户仍然看到 `Invalid Unicode escape sequence`。排查发现第二个（实际使用的）`render_template` 函数在第 349 行，第一个在第 66 行。之前的修改只改了第一个。**修复**：修改第二个 `render_template`，并添加 `Cache-Control: no-cache, no-store, must-revalidate` 响应头，避免浏览器缓存旧页面。
4. **服务器重启**：PID 1608 → 23252，Cache-Control 头部验证通过。

## 模型切换
- 用户要求切换到内置模型（qclaw/modelroute）
- 通过 `/api/settings` POST 更新 config.yaml
- 新增 `builtin-modelroute` 模型条目（base_url: http://127.0.0.1:19000/proxy/llm, api_key: ""）
- `default_model_id` 设置为 `builtin-modelroute`
- sensenova 的三个保留为备用

## 文件变更
- `web/templates/article_detail.html`: h1 增加 data-article-id，JS 变量从 DOM 读取
- `web/server.py`: 第二个 render_template 增加 Cache-Control 响应头
- `config/config.yaml`: 默认模型切换为 builtin-modelroute

## 下一步
- 用户需要在浏览器中**关闭所有标签页、重新打开**后生效（Cache-Control 已添加）
- 模型切换后可直接在系统设置页确认