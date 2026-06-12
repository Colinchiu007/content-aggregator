# 导出格式详细规格

> 版本: 1.0.0  
> 最后更新: 2026-05-27  
> 状态: 基于现有代码反向工程

---

## 1. 概述

### 1.1 支持格式

| 格式 | 标识符 | 默认扩展名 | 用途 |
|------|--------|------------|------|
| Markdown | `markdown` / `md` | `.md` | 通用编辑、版本管理 |
| HTML | `html` / `wechat` | `.html` | 网页发布、公众号 |
| JSON | `json` / `json-compact` | `.json` | 数据交换、API |
| 纯文本 | `txt` | `.txt` | 简单存档 |
| 小红书 | `xiaohongshu` / `xhs` | `.md` | 小红书排版 |
| PDF | `pdf` | `.pdf` | 打印、归档 |

### 1.2 导出器架构

```
exporters/
├── __init__.py      # Exporter 统一入口
├── markdown.py       # to_markdown()
├── html.py          # to_html()
├── json.py          # to_json(), to_json_compact()
├── txt.py           # TXTExporter
├── xiaohongshu.py  # to_xiaohongshu()
└── pdf_exporter.py  # PDFExporter
```

**统一入口**: `Exporter.export(article, format_type)` 自动路由到对应转换器。

---

## 2. Markdown 格式

### 2.1 输出规格

```markdown
# 文章标题

> 原文链接: https://example.com/original  
> 来源: RSS - Example Feed  
> 发布时间: 2026-05-27 22:00:00

## 摘要

文章摘要内容...

---

## 正文

改写后的正文内容，保持原有段落结构。

---

**标签**: #AI #机器学习 #技术  
**改写策略**: REWRITE  
**字数**: 3200
```

### 2.2 实现函数

```python
# exporters/markdown.py
def to_markdown(article: Article) -> str:
    """将 Article 转换为 Markdown 格式"""
    # 1. 标题（H1）
    # 2. 元信息（引用块）
    # 3. 摘要（H2）
    # 4. 分隔线
    # 5. 正文（保持段落）
    # 6. 标签（#tag 格式）
    # 7. 改写元数据（策略、字数）
```

### 2.3 特殊规则

- **图片**: `![alt](url)` 保留原 URL
- **链接**: `[text](url)` 保留原 URL
- **代码块**: 三反引号，保留语言标识
- **表格**: Markdown 表格格式

---

## 3. HTML 格式

### 3.1 输出规格

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文章标题</title>
    <style>
        body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        img { max-width: 100%; height: auto; }
        blockquote { border-left: 4px solid #ccc; padding-left: 16px; color: #666; }
    </style>
</head>
<body>
    <article>
        <h1>文章标题</h1>
        <div class="meta">
            <span>来源: RSS - Example Feed</span>
            <span>发布: 2026-05-27</span>
        </div>
        <div class="summary">
            <strong>摘要:</strong> 文章摘要...
        </div>
        <div class="content">
            <!-- 正文内容，保留 HTML 标签 -->
        </div>
        <div class="tags">
            <span class="tag">#AI</span>
            <span class="tag">#机器学习</span>
        </div>
    </article>
</body>
</html>
```

### 3.2 实现函数

```python
# exporters/html.py
def to_html(article: Article) -> str:
    """将 Article 转换为 HTML 格式"""
    # 1. 完整 HTML5 文档结构
    # 2. 内嵌 CSS（响应式）
    # 3. 元信息（div.meta）
    # 4. 摘要（div.summary）
    # 5. 正文（div.content，保留 HTML）
    # 6. 标签（span.tag）
```

### 3.3 特殊处理

- **Markdown → HTML**: 使用 `markdown` 库转换（如有），或保留原 HTML
- **图片**: `<img src="..." alt="...">`
- **代码高亮**: 可选集成 Pygments（配置开关）

---

## 4. JSON 格式

### 4.1 标准格式（to_json）

```json
{
  "id": "uuid-string",
  "title": "文章标题",
  "original_title": "原标题",
  "content": "正文内容（Markdown 或 HTML）",
  "source": "RSS - Example Feed",
  "source_url": "https://example.com/original",
  "author": "作者名",
  "published_at": "2026-05-27T22:00:00Z",
  "summary": "摘要内容",
  "tags": ["AI", "机器学习", "技术"],
  "word_count": 3200,
  "metadata": {
    "rewritten": true,
    "rewrite_strategy": "REWRITE",
    "original_content": "原文内容...",
    "seo_keywords": ["AI", "机器学习"],
    "seo_description": "SEO 描述..."
  },
  "created_at": "2026-05-27T22:30:00Z",
  "updated_at": "2026-05-27T22:35:00Z"
}
```

### 4.2 紧凑格式（to_json_compact）

```json
{
  "id": "uuid-string",
  "title": "文章标题",
  "content": "正文...",
  "source": "RSS",
  "tags": ["AI", "机器学习"],
  "word_count": 3200
}
```

### 4.3 实现函数

```python
# exporters/json.py
def to_json(article: Article, compact: bool = False) -> str:
    """将 Article 转换为 JSON 格式"""
    # 1. 构建字典（包含所有字段）
    # 2. json.dumps(..., ensure_ascii=False, indent=2)
    # 3. compact=True 时只保留核心字段
```

---

## 5. 纯文本格式（TXT）

### 5.1 输出规格

```
文章标题

原文链接: https://example.com/original
来源: RSS - Example Feed
发布时间: 2026-05-27 22:00:00

────────────────────────────────────

摘要:
文章摘要内容...

────────────────────────────────────

正文:

改写后的正文内容，纯文本格式，无 Markdown/HTML 标签。

标签: #AI #机器学习 #技术
字数: 3200
```

### 5.2 实现类

```python
# exporters/txt.py
class TXTExporter:
    def export(self, article: Article, filename: str | None = None) -> str:
        """导出为纯文本格式"""
        # 1. 标题（无格式）
        # 2. 元信息（键值对）
        # 3. 分隔线
        # 4. 摘要
        # 5. 分隔线
        # 6. 正文（strip_html() 移除标签）
        # 7. 标签
```

### 5.3 特殊处理

- **HTML 标签移除**: 使用 `re.sub(r'<[^>]+>', '', text)`
- **Markdown 语法移除**: 移除 `#`, `**`, `*` 等标记
- **换行保留**: 段落之间空一行

---

## 6. 小红书格式

### 6.1 输出规格

```markdown
#文章标题 #AI #机器学习

正文内容，适配小红书风格：

✨ 亮点 1：xxx
✨ 亮点 2：xxx

📌 要点总结：
• 要点 1
• 要点 2

#AI #机器学习 #技术分享 #干货
```

### 6.2 实现函数

```python
# exporters/xiaohongshu.py
def to_xiaohongshu(article: Article) -> str:
    """将 Article 转换为小红书格式"""
    # 1. 标题转为话题标签（#标题 #关键词）
    # 2. 正文分段（✨ 📌 emoji 分隔）
    # 3. 要点列表（• 符号）
    # 4. 末尾标签（#tag 格式，限制 20 个）
```

### 6.3 特殊规则

- **字数限制**: 正文 ≤ 1000 字（小红书限制）
- **标签数量**: ≤ 20 个
- **emoji**: 适当添加（✨ 📌 💡 ⚡）
- **段落**: 短段落，避免大段文字

---

## 7. PDF 格式

### 7.1 输出规格

- **页面大小**: A4（210 × 297 mm）
- **字体**: 
  - 中文：SimSun / Noto Sans CJK SC
  - 英文：Times New Roman
- **标题**: 18pt，加粗，居中
- **正文**: 12pt，1.5 倍行距
- **页眉**: 文章标题（缩写）
- **页脚**: 页码（"第 X 页"）

### 7.2 实现类

```python
# exporters/pdf_exporter.py
class PDFExporter:
    def export(self, article: Article, output_path: str) -> PDFExportResult:
        """导出为 PDF 格式"""
        # 1. 使用 reportlab 或 weasyprint
        # 2. 注册中文字体（SimSun.ttf）
        # 3. 构建 PDF 文档（标题、元信息、正文、标签）
        # 4. 保存至 output_path
```

### 7.3 配置类

```python
@dataclass
class PDFConfig:
    page_size: str = "A4"
    font_name: str = "SimSun"
    font_size: int = 12
    line_spacing: float = 1.5
    margin_top: int = 50
    margin_bottom: int = 50
    margin_left: int = 50
    margin_right: int = 50
```

### 7.4 依赖

- **reportlab**: `pip install reportlab`
- **中文字体**: 需手动下载 `SimSun.ttf` 放至 `fonts/` 目录

---

## 8. 批量导出

### 8.1 接口

```python
# exporters/__init__.py
class Exporter:
    def export_batch(
        self,
        articles: list[Article],
        format_types: list[str] | None = None
    ) -> list[str]:
        """
        批量导出文章
        
        参数：
            articles: Article 列表
            format_types: 格式列表，默认 ["markdown", "html", "json"]
        
        返回：
            文件路径列表
        """
        # 1. 遍历 articles
        # 2. 对每个 article，遍历 format_types
        # 3. 调用 self.export(article, fmt)
        # 4. 收集文件路径
```

### 8.2 默认行为

```python
# 默认格式
format_types = ["markdown", "html", "json"]

# 输出示例
paths = [
    "./output/exports/文章标题.md",
    "./output/exports/文章标题.html",
    "./output/exports/文章标题.json",
]
```

---

## 9. 文件命名规则

### 9.1 命名格式

```
{安全标题}_{日期}.{ext}
```

**安全标题**: 移除非法字符（`\ / : * ? " < > |`），截取前 50 字符

**日期**: `YYYYMMDD` 格式（可选）

### 9.2 实现

```python
# exporters/__init__.py
def _safe_filename(self, title: str) -> str:
    """生成安全文件名"""
    # 1. 移除非法字符
    safe = re.sub(r'[\\/:*?"<>|]', '_', title)
    # 2. 截取前 50 字符
    return safe[:50]
```

---

## 10. 导出目录结构

### 10.1 默认目录

```
output/
└── exports/
    ├── 文章标题1_20260527.md
    ├── 文章标题1_20260527.html
    ├── 文章标题1_20260527.json
    ├── 文章标题2_20260527.pdf
    └── ...
```

### 10.2 配置

```yaml
# config.yaml
export:
  output_dir: "./output/exports"
  date_suffix: true  # 是否添加日期后缀
  overwrite: false    # 文件已存在时是否覆盖
```

---

## 11. 错误处理

### 11.1 常见错误

| 错误类型 | 原因 | 处理方式 |
|----------|------|----------|
| `FileNotFoundError` | 输出目录不存在 | 自动创建 `mkdir(parents=True)` |
| `PermissionError` | 文件被占用 | 捕获异常，记录警告日志 |
| `UnicodeEncodeError` | 编码问题 | 强制使用 UTF-8 |
| `ReportLabError` | 中文字体缺失 | 提示用户下载字体 |

### 11.2 错误返回

```python
@dataclass
class ExportResult:
    success: bool
    file_path: str | None
    error: str | None
    duration: float = 0.0
```

---

## 12. 测试清单

- [ ] Markdown 导出保留图片链接
- [ ] HTML 导出响应式显示
- [ ] JSON 导出包含全部字段
- [ ] TXT 导出移除所有格式标签
- [ ] 小红书格式字数 ≤ 1000
- [ ] PDF 导出中文显示正常
- [ ] 批量导出多格式同时生成
- [ ] 文件命名非法字符处理

---

## 13. 下一步行动

1. **补充单元测试** - 测试每种导出格式的输出内容
2. **添加 EPUB 格式** - 电子书格式（可选）
3. **优化 PDF 样式** - 提供更美观的 PDF 输出
4. **添加导出进度回调** - 批量导出时显示进度
