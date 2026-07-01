# Markdown 导出器模块

将 Article 转换为 Markdown 格式并导出。

## 输入输出

### 输入
```python
Article(
    title="标题",
    content="正文内容...",
    author="作者",
    source="来源",
    tags=["标签1", "标签2"]
)
```

### 输出
```markdown
# 标题

**作者**: 作者
**来源**: 来源
**标签**: 标签1, 标签2

---

正文内容...
```

## 使用示例

```python
from content_aggregator.exporters.markdown import MarkdownExporter

exporter = MarkdownExporter("./output")
path = exporter.export(article)
print(f"导出到: {path}")
```

## 文件命名

默认使用标题作为文件名（最多 50 字符），自动替换非法字符。