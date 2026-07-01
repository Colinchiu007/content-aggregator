"""Proxy config API route — proxy auto-detection and settings."""

import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.proxy_service import auto_detect_proxy, DEFAULT_PROXY_PORTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy", tags=["代理配置"])

# ── In-memory proxy config (no DB needed for port list) ─────────────────
_proxy_ports: list[str] = list(DEFAULT_PROXY_PORTS)
_detected_proxy: str | None = None


# ── Pydantic schemas ────────────────────────────────────────────────────

class ProxyConfigResponse(BaseModel):
    """Proxy configuration response."""
    ports: list[str] = Field(..., description="Proxy port list to probe")
    auto_detect: bool = Field(default=True, description="Auto-detection enabled")
    detected_proxy: str | None = Field(default=None, description="Currently detected proxy URL")


class UpdateProxyConfigRequest(BaseModel):
    """Update proxy configuration."""
    ports: list[str] = Field(..., min_length=1, description="Proxy port list (at least 1 port)")


class AutoDetectResponse(BaseModel):
    """Auto-detect result."""
    detected_proxy: str | None
    available: bool
    message: str


# ── Endpoints ───────────────────────────────────────────────────────────

@router.get("/config", response_model=ProxyConfigResponse)
async def get_proxy_config() -> ProxyConfigResponse:
    """Get current proxy configuration."""
    return ProxyConfigResponse(
        ports=_proxy_ports,
        auto_detect=True,
        detected_proxy=_detected_proxy,
    )


@router.put(
    "/config",
    response_model=ProxyConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def update_proxy_config(body: UpdateProxyConfigRequest) -> ProxyConfigResponse:
    """Update proxy port list and trigger auto-detection."""
    global _proxy_ports

    _proxy_ports = body.ports

    # Trigger auto-detection with new ports
    detected = await auto_detect_proxy(_proxy_ports)
    global _detected_proxy
    _detected_proxy = detected

    return ProxyConfigResponse(
        ports=_proxy_ports,
        auto_detect=True,
        detected_proxy=_detected_proxy,
    )


@router.post("/auto-detect", response_model=AutoDetectResponse)
async def trigger_auto_detect() -> AutoDetectResponse:
    """Manually trigger proxy auto-detection."""
    global _detected_proxy

    detected = await auto_detect_proxy(_proxy_ports)
    _detected_proxy = detected

    if detected:
        return AutoDetectResponse(
            detected_proxy=detected,
            available=True,
            message=f"已检测到可用代理端口",
        )

    return AutoDetectResponse(
        detected_proxy=None,
        available=False,
        message="未检测到可用代理端口，请检查代理软件是否启动",
    )
