# 封面图显示修复

**时间：** 2026-06-07 12:56–13:01 GMT+8

## 问题
AI生成封面成功后，预览图「生成成功」但是下方显示空白，点「查看」返回 `{"detail":"Not Found"}`

## 根因分析
1. **路径不匹配**：`cover_router.py` 的 `generate-cover` 端点在存储和返回时用的是完整 Windows 路径（如 `C:\Users\邱领\.qclaw\workspace\content-aggregator\data\covers\xxx.png`），但前端用 `/static/${result.path}` 去显示
2. **无服务端点**：`/static/` FastAPI StaticFiles 只挂载了 `web/static/` 目录，`data/covers/` 不在其内

## 修复内容

### server.py
- 新增 `from fastapi.responses import Response`
- 新增 `GET /covers/{filename}` 端点：从 `COVERS_DIR = Path(__file__).parent.parent / "data" / "covers"` 读取，返回对应 MIME 类型的图片

### article_detail.html
- `generateCoverForPublish`: 用 `result.cover_id + '.png'` 构建 `/covers/{filename}` URL
- `loadCoversForPublish`: 用 `c.path.split(/[\\\/]/).pop()` 提取文件名，构建 `/covers/{filename}` URL
- `selectCoverForPublish`: 同上

### cover_router.py
- `api_generate_cover`: 存储和返回的 `path` 改为相对路径 `data/covers/xxx.png`

## 验证
- `POST /api/wechat/generate-cover` → `path: "data\covers\xxx.png"` ✅
- `GET /covers/xxx.png` → 200 ✅