"""Cover 管理路由 — 占位，待实现"""
from fastapi import APIRouter

router = APIRouter(prefix="/covers", tags=["封面管理"])


@router.get("")
async def list_covers():
    return {"items": [], "total": 0}
