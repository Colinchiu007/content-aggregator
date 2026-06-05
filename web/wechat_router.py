"""
微信发布路由 - 排版预览 + 发布到微信公众号

依赖: wechat_publisher/（来自 wewrite toolkit）
"""
import os, json, logging, tempfile, traceback
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse

from wechat_publisher.theme import load_theme, list_themes
from wechat_publisher.converter import WeChatConverter, ConvertResult
from wechat_publisher import publisher as pub
from wechat_publisher import wechat_api as wx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wechat", tags=["wechat"])

# ---- 配置管理 ----

WECHAT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "wechat_publish.json"


def _load_config() -> dict:
    if WECHAT_CONFIG_PATH.exists():
        return json.loads(WECHAT_CONFIG_PATH.read_text(encoding="utf-8"))
    return {"appid": "", "secret": "", "default_theme": "professional-clean"}


def _save_config(cfg: dict):
    WECHAT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    WECHAT_CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_article_content(article_id: str) -> dict:
    """从 article_store 获取文章内容，返回 dict 或 None"""
    from web.server import article_store
    art = article_store.get(article_id)
    if not art:
        raise HTTPException(404, f"文章不存在: {article_id}")
    return art


# ---- API 端点 ----

@router.get("/themes")
async def api_list_themes():
    """列出所有可用排版主题"""
    names = list_themes()
    themes = []
    for name in names:
        try:
            t = load_theme(name)
            themes.append({
                "name": name,
                "display_name": t.name,
                "description": t.description,
            })
        except Exception as e:
            themes.append({"name": name, "display_name": name, "description": str(e)})
    return {"themes": themes}


@router.post("/preview/{article_id}")
async def api_preview_article(
    article_id: str,
    request: Request,
    theme: str = Form(default="professional-clean"),
):
    """预览文章排版效果，返回转换后的 HTML"""
    art = _get_article_content(article_id)
    content = (art.get("content") or "")
    title = art.get("title") or ""

    if not content:
        raise HTTPException(400, "文章内容为空")

    # 构建 Markdown 内容
    md = f"# {title}\n\n{content}" if title else content

    try:
        converter = WeChatConverter(theme_name=theme)
        result: ConvertResult = converter.convert(md)
        return {
            "html": result.html,
            "title": result.title,
            "digest": result.digest,
            "images": result.images,
        }
    except Exception as e:
        logger.error(f"Preview failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"排版失败: {str(e)}")


@router.get("/preview/{article_id}")
async def api_preview_page(
    article_id: str,
    request: Request,
    theme: str = Query(default="professional-clean"),
):
    """预览页面 - 直接在浏览器中显示排版后的文章"""
    art = _get_article_content(article_id)
    content = (art.get("content") or "")
    title = art.get("title") or ""

    if not content:
        return HTMLResponse("<h2>文章内容为空</h2>")

    md = f"# {title}\n\n{content}" if title else content

    try:
        converter = WeChatConverter(theme_name=theme)
        result: ConvertResult = converter.convert(md)
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{result.title} - 排版预览</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #f5f5f5; padding: 20px; }}
        .preview-container {{
            max-width: 677px; margin: 0 auto;
            background: #fff; border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .preview-header {{
            padding: 16px 20px; background: #fafafa;
            border-bottom: 1px solid #eee;
            display: flex; justify-content: space-between; align-items: center;
        }}
        .preview-header h3 {{ font-size: 14px; color: #666; }}
        .preview-header .theme-badge {{
            font-size: 12px; color: #999; background: #f0f0f0;
            padding: 2px 8px; border-radius: 4px;
        }}
        .preview-body {{ padding: 20px; }}
        .preview-footer {{
            padding: 12px 20px; border-top: 1px solid #eee;
            text-align: center; color: #999; font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="preview-container">
        <div class="preview-header">
            <h3>📱 排版预览</h3>
            <span class="theme-badge">{theme} 主题</span>
        </div>
        <div class="preview-body">{result.html}</div>
        <div class="preview-footer">WeChat 兼容排版 | {result.digest[:60]}...</div>
    </div>
</body>
</html>"""
        return HTMLResponse(html)
    except Exception as e:
        return HTMLResponse(f"<h2>排版失败</h2><p>{e}</p>")


@router.post("/publish/{article_id}")
async def api_publish_article(
    article_id: str,
    request: Request,
    theme: str = Form(default="professional-clean"),
    author: str = Form(default=""),
):
    """将文章发布到微信公众号草稿箱"""
    # 检查配置
    cfg = _load_config()
    if not cfg.get("appid") or not cfg.get("secret"):
        raise HTTPException(400, "请先在设置中配置微信公众号 AppID 和 Secret")

    art = _get_article_content(article_id)
    content = (art.get("content") or "")
    title = art.get("title") or ""

    if not content:
        raise HTTPException(400, "文章内容为空")
    if not title:
        raise HTTPException(400, "文章标题为空")

    md = f"# {title}\n\n{content}" if title else content

    try:
        # 1. 排版转换
        converter = WeChatConverter(theme_name=theme)
        result: ConvertResult = converter.convert(md)

        # 2. 获取 access_token
        token = wx.get_access_token(cfg["appid"], cfg["secret"])

        # 3. 发布草稿
        draft = pub.create_draft(
            access_token=token,
            title=result.title or title,
            html=result.html,
            digest=result.digest[:120],
            author=author or None,
        )

        return {
            "success": True,
            "media_id": draft.media_id,
            "title": result.title or title,
            "digest": result.digest[:120],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, f"发布失败: {str(e)}")


@router.get("/config")
async def api_get_config():
    """获取微信发布配置状态（不返回 secret）"""
    cfg = _load_config()
    return {
        "configured": bool(cfg.get("appid") and cfg.get("secret")),
        "appid": cfg.get("appid", ""),
        "default_theme": cfg.get("default_theme", "professional-clean"),
    }


@router.post("/config")
async def api_save_config(
    request: Request,
    appid: str = Form(default=""),
    secret: str = Form(default=""),
    default_theme: str = Form(default="professional-clean"),
):
    """保存微信发布配置"""
    cfg = _load_config()
    if appid:
        cfg["appid"] = appid
    if secret:
        cfg["secret"] = secret
    if default_theme:
        cfg["default_theme"] = default_theme
    _save_config(cfg)
    return {"success": True}


@router.post("/test-connection")
async def api_test_connection(request: Request):
    """测试微信公众号 API 连接"""
    cfg = _load_config()
    if not cfg.get("appid") or not cfg.get("secret"):
        raise HTTPException(400, "请先配置 AppID 和 Secret")
    try:
        token = wx.get_access_token(cfg["appid"], cfg["secret"])
        return {"success": True, "message": "连接成功"}
    except Exception as e:
        raise HTTPException(400, f"连接失败: {str(e)}")


@router.get("/gallery")
async def api_theme_gallery(request: Request):
    """主题画廊（HTML）"""
    names = list_themes()
    theme_infos = []
    for name in names:
        try:
            t = load_theme(name)
            theme_infos.append({"name": name, "display_name": t.name, "description": t.description})
        except:
            theme_infos.append({"name": name, "display_name": name, "description": ""})

    cards_html = ""
    for t in theme_infos:
        cards_html += f"""
        <div class="theme-card" data-theme="{t['name']}">
            <div class="theme-preview" id="preview-{t['name']}">
                <div class="preview-loading">加载预览...</div>
            </div>
            <div class="theme-info">
                <strong>{t['display_name']}</strong>
                <p>{t['description'][:80]}</p>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>排版主题画廊</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: #f0f2f5; padding: 20px; }}
        h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .subtitle {{ color: #666; margin-bottom: 20px; font-size: 14px; }}
        .theme-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 16px;
        }}
        .theme-card {{
            background: #fff; border-radius: 12px; overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06); cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .theme-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.1); }}
        .theme-preview {{
            height: 200px; background: #fafafa;
            display: flex; align-items: center; justify-content: center;
            overflow: hidden; position: relative;
        }}
        .preview-loading {{ color: #ccc; font-size: 13px; }}
        .theme-info {{ padding: 12px 16px; }}
        .theme-info strong {{ font-size: 15px; }}
        .theme-info p {{ font-size: 12px; color: #999; margin-top: 4px; }}
        .theme-demo {{
            font-size: 11px; padding: 12px; text-align: left; width: 100%;
        }}
        .theme-demo h2 {{ font-size: 14px; margin-bottom: 4px; }}
        .theme-demo p {{ font-size: 11px; line-height: 1.5; }}
    </style>
</head>
<body>
    <h1>🎨 排版主题</h1>
    <p class="subtitle">共 {len(theme_infos)} 个主题，全部支持微信暗黑模式</p>
    <div class="theme-grid">{cards_html}</div>
    <script>
        // Load theme preview via /api/wechat/preview/sample?theme=xxx
        // For now just show theme cards
        document.querySelectorAll('.theme-card').forEach(card => {{
            card.addEventListener('click', () => {{
                document.querySelectorAll('.theme-card').forEach(c => c.style.outline = 'none');
                card.style.outline = '2px solid #07c160';
            }});
        }});
    </script>
</body>
</html>"""
    return HTMLResponse(html)


# ---- Web 页面 - 使用 server 中的 Jinja2 templates ----

@router.get("/settings-page", include_in_schema=False)
@router.get("/settings", include_in_schema=False)
async def wechat_settings_page(request: Request):
    """微信发布设置页面 - 使用 Jinja2 模板"""
    from web.server import templates
    cfg = _load_config()
    names = list_themes()
    theme_list = []
    for name in names:
        try:
            t = load_theme(name)
            theme_list.append({"name": name, "display_name": t.name, "description": t.description})
        except:
            theme_list.append({"name": name, "display_name": name, "description": ""})
    return templates.TemplateResponse(
        "wechat_settings.html",
        {"request": request, "config": cfg, "themes": theme_list}
    )
