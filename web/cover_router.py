"""
封面图管理路由（AI 生成 + 列表）

Routes:
  POST  /api/wechat/generate-cover  — AI 生成封面图
  GET   /api/wechat/covers          — 列出已生成的封面

默认封面上传/获取/删除交由 webchat_router.py 处理（/default-cover）。
"""

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Request

from config.loader import load_config
from wechat_publisher.image_gen import generate_image

router = APIRouter(tags=["cover"])

DATA_DIR = Path(__file__).parent.parent / "data"
COVERS_DIR = DATA_DIR / "covers"


def _get_covers() -> list[dict]:
    """Return sorted list of generated covers."""
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    covers = []
    for f in sorted(COVERS_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
        covers.append({
            "id": f.stem,
            "path": str(f.relative_to(COVERS_DIR.parent.parent)),
            "url": f"/covers/{f.name}",
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return covers


@router.post("/api/wechat/generate-cover")
async def generate_cover(
    prompt: str = Form(...),
    size: str = Form("cover"),
    request: Request = None,
):
    """AI 生成封面图，保存到 data/covers/"""
    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    cfg = load_config()
    img_cfg = cfg.get("image", {})
    providers = img_cfg.get("providers", [])
    if not providers and not img_cfg.get("api_key"):
        raise HTTPException(
            status_code=400,
            detail="未配置图片生成 API，请在 config.yaml 中配置 image.providers 或 image.api_key",
        )

    cover_id = uuid.uuid4().hex[:12]
    output_path = str(COVERS_DIR / f"{cover_id}.png")

    try:
        generate_image(prompt, output_path, size=size, config=cfg)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片生成失败: {e}")

    return {"cover_id": cover_id, "url": f"/covers/{cover_id}.png"}


@router.get("/api/wechat/covers")
async def list_covers():
    """列出所有已生成的封面图"""
    return {"covers": _get_covers()}
