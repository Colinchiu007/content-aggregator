"""
封面图管理路由（上传 + AI 生成）

Routes:
  POST   /api/wechat/generate-cover  — AI 生成封面图
  GET    /api/wechat/covers          — 列出已生成的封面
  POST   /api/wechat/default-cover   — 上传/设置默认封面
  GET    /api/wechat/default-cover   — 获取默认封面信息
  DELETE /api/wechat/default-cover   — 删除默认封面
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse

from config.loader import load_config
from wechat_publisher.image_gen import generate_image

router = APIRouter(tags=["cover"])

DATA_DIR = Path(__file__).parent.parent / "data"
COVERS_DIR = DATA_DIR / "covers"
DEFAULT_COVER_FILE = DATA_DIR / "default_cover.json"


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


def _get_default_cover_info() -> dict:
    """Return default cover info from JSON storage."""
    if DEFAULT_COVER_FILE.exists():
        try:
            return json.loads(DEFAULT_COVER_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"exists": False}


@router.post("/api/wechat/generate-cover")
async def generate_cover(
    prompt: str = Form(...),
    size: str = Form("cover"),
    request: Request = None,
):
    """AI 生成封面图，保存到 data/covers/"""
    if not prompt or not prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    # 检查配置中是否有图片生成 API
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


@router.get("/api/wechat/default-cover")
async def get_default_cover():
    """获取默认封面信息"""
    info = _get_default_cover_info()
    return info


@router.post("/api/wechat/default-cover")
async def upload_default_cover(file: UploadFile = File(...)):
    """上传/设置默认封面"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    cover_id = uuid.uuid4().hex[:12]
    output = COVERS_DIR / f"{cover_id}.png"

    try:
        content = await file.read()
        output.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")

    info = {
        "exists": True,
        "cover_id": cover_id,
        "url": f"/covers/{cover_id}.png",
        "path": str(output),
        "size": len(content),
        "updated": datetime.now().isoformat(),
    }
    DEFAULT_COVER_FILE.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "cover_id": cover_id}


@router.delete("/api/wechat/default-cover")
async def delete_default_cover():
    """删除默认封面"""
    if DEFAULT_COVER_FILE.exists():
        DEFAULT_COVER_FILE.unlink()
    return {"success": True}
