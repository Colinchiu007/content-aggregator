"""
微信发布路由 - 排版预览 + 发布到微信公众号

依赖: wechat_publisher/(来自 wewrite toolkit)
"""
import os, json, logging, tempfile, traceback, re, requests, time
from pathlib import Path
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException, Query, File, UploadFile
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
    """从 article_store 获取文章内容,返回 dict 或 None"""
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
    """预览文章排版效果,返回转换后的 HTML"""
    logger.warning(f"[DEBUG] api_preview_article called, article_id={article_id}, theme={theme}")
    art = _get_article_content(article_id)
    content = (art.get("content") or "")
    title = art.get("title") or ""

    if not content:
        raise HTTPException(400, "文章内容为空")

    # 内容质量检测:识别被 LLM 推理链污染的数据
    cn_ratio = sum(1 for c in content if '\u4e00' <= c <= '\u9fff') / max(len(content), 1)
    reasoning_indicators = ['Evaluate the Input', 'Step 1:', '**Plan:**', 'reasoning', '思维链', '推理过程']
    is_reasoning = any(ind in content for ind in reasoning_indicators) or (
        len(content) > 200 and cn_ratio < 0.3 and content[0].isdigit()
    )

    if is_reasoning or len(content.strip()) < 50:
        warning_html = (
            '<div style="padding:24px;text-align:center;background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;margin:16px 0">'  
            '<p style="font-size:15px;color:#92400e;margin:0 0 8px;font-weight:700">⚠️ 文章内容异常</p>'
            '<p style="font-size:13px;color:#a16207;margin:0;line-height:1.6">'  
            f'该文章的 content 字段可能存储了 LLM 推理链而非正常文章内容（中文占比 {cn_ratio:.0%}）。'
            '<br>请重新采集并改写此文章，或选择其他正常文章预览。</p>'
            '</div>'
        )
        return {
            "html": warning_html,
            "title": title,
            "digest": "文章内容异常，需要重新改写",
            "images": [],
            "warning": "content_quality_issue",
        }

    # 构建 Markdown 内容
    md = f"# {title}\n\n{content}" if title else content

    try:
        converter = WeChatConverter(theme_name=theme)
        result: ConvertResult = converter.convert(md)
        
        return {
            "html": result.html,  # 已有内联样式，无需再加 <style> 标签
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

    # 内容质量检测(同 POST)
    cn_ratio = sum(1 for c in content if '\u4e00' <= c <= '\u9fff') / max(len(content), 1)
    reasoning_indicators = ['Evaluate the Input', 'Step 1:', '**Plan:**', 'reasoning']
    is_reasoning = any(ind in content for ind in reasoning_indicators) or (
        len(content) > 200 and cn_ratio < 0.3 and content[0].isdigit()
    )

    if is_reasoning or len(content.strip()) < 50:
        return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>内容异常</title></head>
<body style="padding:24px;text-align:center;background:#fef3c7">
<h2 style="color:#92400e">⚠️ 文章内容异常</h2>
<p>该文章 content 字段可能存储了 LLM 推理链而非正常文章内容（中文占比 {cn_ratio:.0%}）。</p>
<p>请重新采集并改写此文章。</p>
</body></html>""")

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
        * {{ margin:0; padding:0; box-sizing: border-box; }}
        body {{ background: #f5f5f5; padding: 20px; }}
        .preview-container {{
            max-width: 677px; margin:0 auto;
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
    cover_id: str = Form(default=""),
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

        # 2. 获取或生成 thumb_media_id
        thumb_media_id = None
        
        # 如果提供了 cover_id，使用指定的封面（优先级 P1：AI 生成 或 自定义上传）
        if cover_id:
            # 先尝试从 config 中的 covers 列表查找（旧版传入机制）
            covers = cfg.get("covers", [])
            cover = next((c for c in covers if c.get("id") == cover_id), None)
            cover_path = None
            if cover:
                if cover.get("media_id"):
                    thumb_media_id = cover["media_id"]
                else:
                    cover_path = Path(__file__).parent.parent / "data" / cover["path"]
            else:
                # 再尝试从 data/covers/ 目录直接查找（支持 AI 生成封面等直接存储的封面）
                direct_path = Path(__file__).parent.parent / "data" / "covers" / f"{cover_id}.png"
                if direct_path.exists():
                    cover_path = direct_path
                else:
                    logger.warning(f"Cover not found: {cover_id} (checked config and data/covers/)")

            if cover_path and cover_path.exists():
                try:
                    token_upload = wx.get_access_token(cfg["appid"], cfg["secret"])
                    thumb_media_id = wx.upload_thumb(token_upload, str(cover_path))
                    if thumb_media_id and cover:
                        # config 中的封面缓存 media_id
                        cover["media_id"] = thumb_media_id
                        cfg["covers"] = covers
                        _save_config(cfg)
                except Exception as e:
                    logger.warning(f"Cover upload failed: {e}")
        
        # 如果未指定封面或封面处理失败，按优先级：正文首图 → 默认封面 → 绿色占位图（P2 → P3 → 保底）
        if not thumb_media_id:
            # 优先级1：从正文提取首张图片
            body_images = result.images if hasattr(result, 'images') and result.images else []
            if not body_images:
                # 也尝试从原始 content 中提取
                body_images = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', content)
            if body_images:
                try:
                    img_url = body_images[0]
                    logger.info(f"从正文提取首图作为封面: {img_url}")
                    img_resp = requests.get(img_url, timeout=15)
                    if img_resp.status_code == 200:
                        # 保存到临时文件，upload_thumb 需要文件路径
                        suffix = Path(img_url.split("?")[0]).suffix or ".jpg"
                        import tempfile
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                        tmp.write(img_resp.content)
                        tmp_path = tmp.name
                        tmp.close()
                        try:
                            token_up = wx.get_access_token(cfg["appid"], cfg["secret"])
                            thumb_media_id = wx.upload_thumb(token_up, tmp_path)
                            if thumb_media_id:
                                logger.info(f"正文首图已上传为封面, media_id={thumb_media_id}")
                        finally:
                            try:
                                Path(tmp_path).unlink(missing_ok=True)
                            except Exception:
                                pass
                    else:
                        logger.warning(f"正文图片下载失败: HTTP {img_resp.status_code}")
                except Exception as e_img:
                    logger.warning(f"正文图片提取失败: {e_img}")
            
            # 优先级2：系统默认封面图（本地文件 + 缓存 media_id）
            if not thumb_media_id:
                default_cover_path = Path(__file__).parent.parent / "data" / "covers" / "default_cover.png"
                if default_cover_path.exists():
                    # 检查缓存的 media_id 是否仍有效（临时素材有效期 3 天，提前半天刷新）
                    cached_mid = cfg.get("default_thumb_media_id")
                    cached_at = cfg.get("default_thumb_uploaded_at", 0)
                    now_ts = time.time()
                    if cached_mid and (now_ts - cached_at) < 2.5 * 86400:
                        thumb_media_id = cached_mid
                        logger.info(f"复用缓存的默认封面 media_id: {thumb_media_id}")
                    else:
                        try:
                            token_up = wx.get_access_token(cfg["appid"], cfg["secret"])
                            thumb_media_id = wx.upload_thumb(token_up, str(default_cover_path))
                            if thumb_media_id:
                                cfg["default_thumb_media_id"] = thumb_media_id
                                cfg["default_thumb_uploaded_at"] = now_ts
                                _save_config(cfg)
                                logger.info(f"默认封面上传成功, media_id={thumb_media_id}, 缓存至 {(now_ts + 2.5*86400):.0f}")
                        except Exception as e_default:
                            logger.warning(f"系统默认封面上传失败: {e_default}")
            
            # 优先级3：绿色占位图（最终保底）
            if not thumb_media_id:
                from PIL import Image
                img = Image.new("RGB", (900, 500), color="#07C160")
                import tempfile
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                img.save(tmp, format="JPEG", quality=85)
                tmp_path = tmp.name
                tmp.close()
                try:
                    token_up = wx.get_access_token(cfg["appid"], cfg["secret"])
                    thumb_media_id = wx.upload_thumb(token_up, tmp_path)
                    if not thumb_media_id:
                        raise HTTPException(500, "上传默认封面失败，无法发布")
                finally:
                    try:
                        Path(tmp_path).unlink(missing_ok=True)
                    except Exception:
                        pass

        # 3. 获取 access_token
        token = wx.get_access_token(cfg["appid"], cfg["secret"])

        # 4. 发布草稿
        draft = pub.create_draft(
            access_token=token,
            title=result.title or title,
            html=result.html,
            digest=result.digest[:120],
            author=author or None,
            thumb_media_id=thumb_media_id,
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


# ---- 默认封面管理 ----

DEFAULT_COVER_PATH = Path(__file__).parent.parent / "data" / "covers" / "default_cover.png"

@router.get("/default-cover")
async def api_get_default_cover():
    """获取默认封面信息"""
    if DEFAULT_COVER_PATH.exists():
        return {
            "exists": True,
            "url": "/covers/default_cover.png",
            "size": DEFAULT_COVER_PATH.stat().st_size,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(DEFAULT_COVER_PATH.stat().st_mtime)),
        }
    return {"exists": False}


@router.post("/default-cover")
async def api_upload_default_cover(request: Request, file: UploadFile = File(...)):
    """上传/更新系统默认封面图（本地存储，发布时实时上传到微信）"""
    allowed = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed:
        raise HTTPException(400, f"不支持的类型: {file.content_type}，请上传 JPG/PNG/GIF/WebP")
    DEFAULT_COVER_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件超过 10MB")
    DEFAULT_COVER_PATH.write_bytes(content)
    return {"success": True, "url": "/covers/default_cover.png", "size": len(content)}


@router.delete("/default-cover")
async def api_delete_default_cover():
    """删除默认封面"""
    if DEFAULT_COVER_PATH.exists():
        DEFAULT_COVER_PATH.unlink()
    return {"success": True}


@router.get("/config")
async def api_get_config():
    """获取微信发布配置状态(不返回 secret)"""
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
    """主题画廊(HTML)"""
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
        * {{ margin:0; padding:0; box-sizing: border-box; }}
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
    <p class="subtitle">共 {len(theme_infos)} 个主题,全部支持微信暗黑模式</p>
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
        {"request": request, "cfg": cfg, "theme_list": theme_list}
    )
