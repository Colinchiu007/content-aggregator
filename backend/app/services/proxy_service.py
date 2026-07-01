"""Proxy auto-detection service — probe ports and detect available proxy.

Features:
- TCP connect test per port (async)
- Iterate configured ports, return first available
- Graceful fallback when none available
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)

# ── Default ports to probe ──────────────────────────────────────────────
DEFAULT_PROXY_PORTS = ["7890", "12334", "7892"]

# ── Proxy URL template ──────────────────────────────────────────────────
PROXY_URL_TEMPLATE = "socks5://127.0.0.1:{port}"


async def probe_port(host: str = "127.0.0.1", port: int | str = 7890, timeout: float = 2.0) -> bool:
    """Test if a TCP port is reachable.

    Args:
        host: Target host (default 127.0.0.1)
        port: Port number (int or str)
        timeout: Connection timeout in seconds

    Returns:
        True if port is open and accepting connections
    """
    port = int(port)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, asyncio.TimeoutError, OSError):
        return False


async def auto_detect_proxy(ports: list[str] | None = None) -> str | None:
    """Iterate port list and return first available proxy URL.

    Args:
        ports: List of port strings to try (defaults to DEFAULT_PROXY_PORTS)

    Returns:
        Proxy URL string (e.g. "socks5://127.0.0.1:7890") or None if none available
    """
    ports = ports or list(DEFAULT_PROXY_PORTS)
    if not ports:
        return None

    for port in ports:
        if await probe_port(port=port):
            logger.info("Proxy detected: port %s", port)
            return PROXY_URL_TEMPLATE.format(port=port)

    logger.warning("No proxy port available among: %s", ports)
    return None
