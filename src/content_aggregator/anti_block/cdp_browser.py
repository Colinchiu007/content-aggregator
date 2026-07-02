"""
CDP 浏览器管理器 — Playwright CDP 浏览器生命周期管理

从 MediaCrawler CDPBrowserManager 适配：
- 自动检测 Chrome/Edge 浏览器路径
- 启动浏览器并通过 CDP 连接
- 复用用户已有浏览器（CDP_CONNECT_EXISTING）
- stealth.min.js 反检测脚本注入
- 防检测启动参数

集成到 content-aggregator anti_block 模块，配合 BaseCollector 使用。
"""

import asyncio
import logging
import os
import platform
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def find_browser_paths() -> list[str]:
    """自动检测系统已安装的 Chrome/Edge 浏览器路径"""
    system = platform.system()
    paths = []

    if system == "Windows":
        candidates = [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        ]
    elif system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/microsoft-edge",
            "/snap/bin/chromium",
        ]

    for p in candidates:
        if os.path.isfile(p):
            paths.append(p)

    return paths


def find_available_port(start: int = 9222, max_attempts: int = 100) -> int:
    """从 start 开始找一个可用端口"""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"无法找到可用端口 (尝试 {start}~{start + max_attempts})")


def get_browser_launch_args(debug_port: int, headless: bool = False,
                            user_data_dir: str | None = None) -> list[str]:
    """生成浏览器启动参数（反检测优化）"""
    args = [
        f"--remote-debugging-port={debug_port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-background-networking",
        "--disable-features=ChromeWhatsNewUI",
        "--disable-features=TranslateUI",
        "--disable-infobars",
        f"--window-size=1920,1080",
        "--start-maximized",
        "--disable-blink-features=AutomationControlled",
        "--disable-popup-blocking",
        "--disable-notifications",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
    ]
    if headless:
        args.append("--headless=new")
    if user_data_dir:
        args.append(f"--user-data-dir={user_data_dir}")
    return args


class CDPBrowserManager:
    """
    浏览器 CDP 生命周期管理器

    使用方式：
        mgr = CDPBrowserManager()
        context = await mgr.launch(headless=False)
        page = await context.new_page()
        await page.goto("https://example.com")
        # ... 操作 ...
        await mgr.close()
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._browser_context = None
        self._browser_process: subprocess.Popen | None = None  # type: ignore[usage]
        self._debug_port: int | None = None
        self._cleaned = False

    # ── 生命周期 ──────────────────────────────────────

    async def launch(self, headless: bool = False,
                     browser_path: str | None = None,
                     user_data_dir: str | None = None,
                     connect_existing: bool = False,
                     proxy: str | None = None,
                     stealth_js_path: str | None = None) -> "BrowserContext":  # type: ignore[name-defined]
        """
        启动或连接浏览器，返回 Playwright BrowserContext。

        Args:
            headless: 是否无头模式
            browser_path: 浏览器可执行路径（None 则自动检测）
            user_data_dir: 用户数据目录（保存登录状态）
            connect_existing: 连接已有浏览器（如 chrome://inspect）
            proxy: HTTP 代理地址（如 http://127.0.0.1:8080）
            stealth_js_path: stealth.min.js 路径（注入反检测脚本）

        Returns:
            playwright.async_api.BrowserContext
        """
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        if connect_existing:
            context = await self._connect_existing(proxy)
        else:
            context = await self._launch_new(headless, browser_path,
                                            user_data_dir, proxy)

        # stealth 脚本注入
        if stealth_js_path and os.path.exists(stealth_js_path):
            try:
                await context.add_init_script(path=stealth_js_path)
                logger.info("[CDP] stealth.min.js 已注入")
            except Exception as e:
                logger.warning(f"[CDP] stealth 注入失败: {e}")

        self._browser_context = context
        logger.info("[CDP] 浏览器就绪")
        return context

    async def close(self, keep_browser_open: bool = False):
        """关闭浏览器，释放资源"""
        if self._cleaned:
            return
        self._cleaned = True

        try:
            if self._browser_context:
                try:
                    await self._browser_context.close()
                except Exception:
                    pass
                self._browser_context = None
        except Exception:
            pass

        try:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
        except Exception:
            pass

        if self._browser_process and not keep_browser_open:
            try:
                self._browser_process.terminate()
                self._browser_process.wait(timeout=5)
            except Exception:
                try:
                    self._browser_process.kill()
                except Exception:
                    pass
            self._browser_process = None

        logger.info("[CDP] 浏览器资源已清理")

    # ── 内部方法 ──────────────────────────────────────

    async def _launch_new(self, headless: bool, browser_path: str | None,
                          user_data_dir: str | None,
                          proxy: str | None) -> "BrowserContext":  # type: ignore[name-defined]
        """启动新浏览器进程"""
        # 1. 找浏览器
        if not browser_path:
            paths = find_browser_paths()
            if not paths:
                raise RuntimeError(
                    "未找到 Chrome/Edge 浏览器。请手动安装，"
                    "或通过 browser_path 参数指定路径。")
            browser_path = paths[0]
            logger.info(f"[CDP] 自动检测到浏览器: {browser_path}")

        # 2. 找端口
        self._debug_port = find_available_port()

        # 3. 启动浏览器进程
        args = get_browser_launch_args(self._debug_port, headless, user_data_dir)
        logger.info(f"[CDP] 启动浏览器 (port={self._debug_port}, headless={headless})")
        self._browser_process = subprocess.Popen(
            [browser_path] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # 4. 等待就绪
        await self._wait_for_browser_ready(timeout=30)

        # 5. CDP 连接
        ws_url = await self._get_ws_url(self._debug_port)
        connect_kwargs: dict = {"ws_endpoint": ws_url}
        if proxy:
            connect_kwargs["proxy"] = {"server": proxy}
        self._browser = await self._playwright.chromium.connect_over_cdp(**connect_kwargs)  # type: ignore[attr-defined]

        # 6. 创建/复用 context
        if self._browser.contexts:
            ctx = self._browser.contexts[0]
        else:
            ctx = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
        return ctx

    async def _connect_existing(self, proxy: str | None) -> "BrowserContext":  # type: ignore[name-defined]
        """连接已有浏览器（用户手动打开 chrome://inspect）"""
        # 默认端口 9222，也可从环境变量读取
        port = int(os.environ.get("CDP_DEBUG_PORT", "9222"))
        self._debug_port = port

        logger.info(f"[CDP] 等待已有浏览器连接 (port={port})...")
        logger.info("[CDP] 请在 Chrome 中打开 chrome://inspect/#remote-debugging 并确认")

        # 等端口就绪
        for i in range(60):
            if await self._test_port(port):
                break
            if i % 10 == 0 and i > 0:
                logger.info(f"[CDP] 等待浏览器连接... ({i}s)")
            await asyncio.sleep(1)
        else:
            raise RuntimeError(
                f"无法连接已有浏览器 (port={port})。请确保:\n"
                "  1. 浏览器已开启远程调试\n"
                "  2. chrome://inspect/#remote-debugging 已打开\n"
                "  3. 端口正确")

        # Chrome 136+ 使用直接 ws 连接
        ws_url = f"ws://127.0.0.1:{port}/devtools/browser"
        try:
            self._browser = await self._playwright.chromium.connect_over_cdp(  # type: ignore[attr-defined]
                ws_url, timeout=30000)
        except Exception:
            # fallback: 通过 /json/version 发现
            ws_url = await self._get_ws_url(port)
            self._browser = await self._playwright.chromium.connect_over_cdp(ws_url)  # type: ignore[attr-defined]

        # 复用已有 context
        if self._browser.contexts:
            return self._browser.contexts[0]
        ctx_kwargs = {"viewport": {"width": 1920, "height": 1080}}
        if proxy:
            ctx_kwargs["proxy"] = {"server": proxy}
        return await self._browser.new_context(**ctx_kwargs)

    async def _wait_for_browser_ready(self, timeout: int = 30) -> None:
        """等待浏览器 CDP 端口就绪"""
        port = self._debug_port
        for i in range(timeout):
            if await self._test_port(port):
                return
            await asyncio.sleep(1)
        raise RuntimeError(f"浏览器启动超时 ({timeout}s)")

    async def _test_port(self, port: int) -> bool:
        """测试端口是否可连接"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._test_port_sync, port)
        except Exception:
            return False

    @staticmethod
    def _test_port_sync(port: int) -> bool:
        """同步 TCP 端口测试"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            return s.connect_ex(("127.0.0.1", port)) == 0

    async def _get_ws_url(self, port: int) -> str:
        """从浏览器获取 WebSocket 调试 URL"""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/json/version",
                                    timeout=10)
            resp.raise_for_status()
            data = resp.json()
            ws = data.get("webSocketDebuggerUrl")
            if not ws:
                raise RuntimeError(f"浏览器未返回 WebSocket URL (port={port})")
            return ws


# ── 便捷入口 ──────────────────────────────────────

async def create_cdp_context(
    headless: bool = False,
    connect_existing: bool = True,
    browser_path: str | None = None,
    user_data_dir: str | None = None,
    stealth_js_path: str | None = None,
) -> tuple:
    """
    一键创建 CDP 浏览器上下文。

    Returns:
        (CDPBrowserManager, BrowserContext) — 使用完后调用 mgr.close()
    """
    mgr = CDPBrowserManager()
    ctx = await mgr.launch(
        headless=headless,
        browser_path=browser_path,
        user_data_dir=user_data_dir,
        connect_existing=connect_existing,
        stealth_js_path=stealth_js_path,
    )
    return mgr, ctx
