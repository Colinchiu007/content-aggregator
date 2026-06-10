"""
Content Aggregator - Web 管理界面

FastAPI + Jinja2，提供可视化操作界面。

启动方式：
    python scripts/web.py              # 默认 http://localhost:8080
    python scripts/web.py --port 9000  # 自定义端口

功能：
    - 仪表盘：数据源状态、最近采集、汇总统计
    - 数据源管理：查看/启用/禁用配置的数据源
    - 文章列表：浏览已采集文章，查看详情
    - 采集任务：触发单源/全源采集，实时查看进度
    - 手动输入：粘贴内容 → 改写 → 导出
    - 配置管理：在线查看和编辑 config.yaml
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# 将父目录添加到 sys.path，使 `import web.xxx` 可用
PARENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PARENT_DIR))

from fastapi import FastAPI, Request, Form, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from loguru import logger

from loguru import logger

# 共享认证模块（已禁用，强制使用本地认证）
# try:
#     sys.path.insert(0, str(Path(__file__).parent.parent.parent / "team"))
#     from shared.auth.auth_routes import router as auth_router
#     from shared.auth.jwt_handler import get_user_from_token
#     AUTH_ENABLED = True
#     logger.info("已加载共享认证模块")
# except ImportError:
#     # Fallback：加载本地认证模块
#     try:
#         from web.auth_router import router as auth_router
#         from web.auth_router import get_current_user as get_user_from_token
#         AUTH_ENABLED = True
#         logger.info("已加载本地认证模块（web/auth_router.py）")
#     except ImportError:
#         AUTH_ENABLED = False
#         logger.warning("认证模块未找到，使用无认证模式")

# 强制使用本地认证模块
from web.auth_router import router as auth_router
from web.auth_router import get_current_user as get_user_from_token
AUTH_ENABLED = True
logger.info("已强制启用本地认证模块（/api/auth 路由）")

# 先把 web 目录加到 sys.path（settings_crypto 在同一目录）
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from settings_crypto import encrypt_config, decrypt_config

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.models import Article, Content
from content_aggregator.strategy_store import RewriteStrategyStore
from content_aggregator.processors.asr_processor import ASRConfig
from server_scheduler import BackgroundScheduler


# ========================================================================
# 自定义 render_template（替代 FastAPI 默认的）
# ========================================================================

def render_template(template_name: str, context: dict) -> HTMLResponse:
    """渲染 Jinja2 模板，强制禁止浏览器缓存"""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(template_name)
    html = template.render(**context)
    from fastapi.responses import Response
    return Response(content=html, media_type="text/html",
                    headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                             "Pragma": "no-cache",
                             "Expires": "0"})


# ========================================================================
# 配置加载
# ========================================================================

def load_config(config_path: str | None = None) -> dict:
    """加载 YAML 配置文件（自动解密 API Key）"""
    import yaml

    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).parent.parent / "config" / "config.yaml"

    if path.exists():
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        decrypt_config(config)
        return config
    return {}


def save_config(config: dict, config_path: str | None = None) -> bool:
    """保存配置到 YAML 文件（自动加密 API Key）"""
    import yaml

    path = Path(config_path) if config_path else Path(__file__).parent.parent / "config" / "config.yaml"
    try:
        # 加密敏感字段后再写入
        config_copy = encrypt_config({k: v for k, v in config.items()})
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config_copy, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        return False


# ========================================================================
# 文章存储（内存 + 文件缓存）
# ========================================================================

class ArticleStore:
    """
    文章存储：内存缓存 + JSON 文件持久化

    设计决策：Web UI 场景下数据量不大（百级文章），
    用内存 dict + 定期 JSON dump 比 SQLite 更轻量。
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.articles: list[dict] = []
        self._load()

    def _load(self):
        """从 JSON 文件加载"""
        cache_file = self.data_dir / "articles_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    self.articles = json.load(f)
            except Exception:
                self.articles = []

    def save(self):
        """持久化到 JSON 文件"""
        cache_file = self.data_dir / "articles_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.articles, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"保存文章缓存失败: {e}")

    def _is_duplicate(self, article: dict) -> bool:
        """按 title+source_url 判断重复"""
        title = article.get("title", "").strip()
        source_url = article.get("source_url", "").strip()
        if not title:
            return False
        for a in self.articles:
            if a.get("title", "").strip() == title and a.get("source_url", "").strip() == source_url:
                return True
        return False

    def add(self, article: dict) -> bool:
        """添加文章，重复则跳过。返回是否成功添加"""
        if self._is_duplicate(article):
            logger.info(f"去重跳过: {article.get('title', '')[:30]}")
            return False
        if not article.get("id"):
            article["id"] = str(uuid.uuid4())
        article["collected_at"] = datetime.now().isoformat()
        self.articles.insert(0, article)  # 最新的在前面
        self.save()
        return True

    def get_by_id(self, article_id: str) -> dict | None:
        """按 ID 获取单篇文章"""
        for a in self.articles:
            if a.get("id") == article_id:
                return a
        return None

    def add_batch(self, articles: list[dict]) -> int:
        """批量添加，自动去重。返回实际添加数量"""
        added = []
        now = datetime.now().isoformat()
        for a in articles:
            if self._is_duplicate(a):
                logger.info(f"去重跳过: {a.get('title', '')[:30]}")
                continue
            if not a.get("id"):
                a["id"] = str(uuid.uuid4())
            a["collected_at"] = now
            added.append(a)
        self.articles = added + self.articles
        self.save()
        return len(added)

    def get_all(self, page: int = 1, per_page: int = 20, source: str | None = None) -> dict:
        """分页获取文章"""
        filtered = self.articles
        if source:
            filtered = [a for a in filtered if a.get("source") == source]

        total = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page
        items = filtered[start:end]

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        }

    def get(self, article_id: str) -> dict | None:
        """按 ID 获取单篇文章（wechat_router 调用接口）"""
        return self.get_by_id(article_id)

    def delete(self, article_id: str) -> bool:
        """删除文章"""
        for i, a in enumerate(self.articles):
            if a.get("id") == article_id:
                self.articles.pop(i)
                self.save()
                return True
        return False

    def clear(self):
        """清空"""
        self.articles = []
        self.save()

    def get_sources(self) -> list[dict]:
        """获取文章来源统计"""
        source_count: dict[str, int] = {}
        for a in self.articles:
            src = a.get("source", "unknown")
            source_count[src] = source_count.get(src, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(source_count.items(), key=lambda x: -x[1])]


# ========================================================================
# 任务管理（后台采集任务）
# ========================================================================

class TaskManager:
    """后台采集任务管理"""

    def __init__(self):
        self.tasks: dict[str, dict] = {}
        self._async_tasks: dict[str, asyncio.Task] = {}  # 存储 asyncio.Task 引用

    def create(self, task_type: str, description: str = "") -> str:
        """创建任务，返回 task_id"""
        task_id = f"task_{int(time.time())}_{id(self) % 10000}"
        self.tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "description": description,
            "status": "pending",  # pending / running / done / error / cancelled
            "progress": 0,
            "message": "",
            "result": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
        }
        return task_id

    def register_async_task(self, task_id: str, async_task: asyncio.Task):
        """注册 asyncio.Task 对象（用于取消）"""
        self._async_tasks[task_id] = async_task

    def cancel(self, task_id: str) -> bool:
        """取消任务（仅 pending/running 可取消）"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task["status"] not in ("pending", "running"):
            return False  # 已完成/失败/已取消，不能取消
        
        # 1. 取消 asyncio.Task
        async_task = self._async_tasks.get(task_id)
        if async_task and not async_task.done():
            async_task.cancel()
            del self._async_tasks[task_id]
        
        # 2. 更新任务状态
        self.update(task_id, status="cancelled", message="任务已取消")
        return True

    def update(self, task_id: str, status: str | None = None, progress: int | None = None,
               message: str | None = None, result: Any = None):
        """更新任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return
        if status:
            task["status"] = status
        if progress is not None:
            task["progress"] = progress
        if message is not None:
            task["message"] = message
        if result is not None:
            task["result"] = result
        if status == "running" and not task["started_at"]:
            task["started_at"] = datetime.now().isoformat()
        if status in ("done", "error", "cancelled"):
            task["finished_at"] = datetime.now().isoformat()

    def get(self, task_id: str) -> dict | None:
        return self.tasks.get(task_id)

    def get_all(self) -> list[dict]:
        return list(self.tasks.values())


# ========================================================================
# FastAPI 应用
# ========================================================================

# 初始化
BASE_DIR = Path(__file__).parent
CONFIG = load_config()

app = FastAPI(title="Content Aggregator", version="1.0.0")

# 请求日志中间件（调试用：记录所有请求路径）
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    start_time = time.time()
    
    # 记录请求信息
    client_host = request.client.host if request.client else "unknown"
    print(f"[REQUEST] {request.method} {request.url.path} from {client_host}")
    
    # 执行请求
    response = await call_next(request)
    
    # 记录响应信息
    process_time = time.time() - start_time
    print(f"[RESPONSE] {request.method} {request.url.path} -> {response.status_code} ({process_time:.3f}s)")
    
    return response

# 静态文件服务
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# 封面图服务 - 从 data/covers/ 目录提供图片
COVERS_DIR = Path(__file__).parent.parent / "data" / "covers"
@app.get("/covers/{filename}")
async def serve_cover(filename: str):
    """提供封面图文件"""
    file_path = COVERS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    ext = file_path.suffix.lower()
    media_type = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}.get(ext, "application/octet-stream")
    return Response(content=file_path.read_bytes(), media_type=media_type)

# 模板（绕过 Starlette Jinja2Templates，直接使用 Jinja2，修复 unhashable type: 'dict' 错误）
jinja_env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    auto_reload=True,
)

# 认证路由（如果可用）
if AUTH_ENABLED:
    app.include_router(auth_router)
    logger.info("已启用共享认证模块（/api/auth 路由）")


# 重置密码页面（GET /auth/reset-password）
@app.get("/auth/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    """重置密码页面（GET 请求，显示 HTML 表单）"""
    token = request.query_params.get("token")
    print(f"[RESET-PAGE] Received request with token: {token[:30] if token else 'None'}...")
    
    if not token:
        html = "<html><body style='font-family: sans-serif; padding: 40px; text-align: center;'><h1>无效的重置链接</h1><p>缺少 token 参数。</p><p><a href='/auth/forgot'>重新申请密码重置</a></p></body></html>"
        return HTMLResponse(content=html, status_code=400)
    
    # 验证 token
    from web.auth_router import decode_token
    payload = decode_token(token)
    if not payload:
        html = "<html><body style='font-family: sans-serif; padding: 40px; text-align: center;'><h1>重置链接已过期</h1><p>请重新申请密码重置。</p><p><a href='/auth/forgot'>重新申请</a></p></body></html>"
        return HTMLResponse(content=html, status_code=400)
    
    print(f"[RESET-PAGE] Token valid: user_id={payload.get('sub')}, username={payload.get('username')}")
    
    # Token 有效，显示重置密码表单
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <title>重置密码 - Content Aggregator</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
        .auth-container {{ width: 100%; max-width: 400px; padding: 20px; }}
        .auth-card {{ background: white; border-radius: 12px; padding: 40px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }}
        h1 {{ font-size: 24px; color: #1a1a1a; margin-bottom: 8px; }}
        .subtitle {{ color: #666; font-size: 14px; margin-bottom: 32px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; font-size: 14px; font-weight: 500; color: #333; margin-bottom: 8px; }}
        input {{ width: 100%; padding: 12px; border: 2px solid #e1e5e9; border-radius: 8px; font-size: 14px; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 12px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }}
        button:hover {{ transform: translateY(-2px); }}
        button:disabled {{ opacity: 0.6; cursor: not-allowed; transform: none; }}
        .error-message {{ background: #fee; color: #c33; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; display: none; }}
        .error-message.show {{ display: block; }}
        .success-message {{ background: #d4edda; color: #155724; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; display: none; }}
        .success-message.show {{ display: block; }}
        .links {{ margin-top: 24px; text-align: center; font-size: 14px; }}
        .links a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .links a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="auth-container">
        <div class="auth-card">
            <h1>🔑 重置密码</h1>
            <p class="subtitle">请输入新密码</p>
            
            <div class="error-message" id="errorEl"></div>
            <div class="success-message" id="successEl"></div>
            
            <form id="form">
                <div class="form-group">
                    <label for="password">新密码</label>
                    <input type="password" id="password" placeholder="请输入新密码（至少6位）" required minlength="6">
                </div>
                <div class="form-group">
                    <label for="confirmPassword">确认新密码</label>
                    <input type="password" id="confirmPassword" placeholder="请再次输入新密码" required minlength="6">
                </div>
                <button type="submit" id="btn">重置密码</button>
            </form>
            
            <div class="links" id="links" style="display: none;">
                <a href="/auth/login">返回登录</a>
            </div>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('form');
        const btn = document.getElementById('btn');
        const errorEl = document.getElementById('errorEl');
        const successEl = document.getElementById('successEl');
        const links = document.getElementById('links');
        
        form.addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            
            if (password.length < 6) {{
                errorEl.textContent = '密码长度至少6位';
                errorEl.classList.add('show');
                return;
            }}
            
            if (password !== confirmPassword) {{
                errorEl.textContent = '两次输入的密码不一致';
                errorEl.classList.add('show');
                return;
            }}
            
            btn.disabled = true;
            btn.textContent = '重置中...';
            errorEl.classList.remove('show');
            
            try {{
                const resp = await fetch('/api/auth/reset-password', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{
                        token: '{token}',
                        new_password: password
                    }})
                }});
                
                const data = await resp.json();
                
                if (resp.ok && data.success) {{
                    successEl.textContent = '密码重置成功！正在跳转到登录页面...';
                    successEl.classList.add('show');
                    form.style.display = 'none';
                    links.style.display = '';
                    
                    setTimeout(() => {{
                        window.location.href = '/auth/login';
                    }}, 2000);
                }} else {{
                    errorEl.textContent = data.detail || '重置失败，请重试';
                    errorEl.classList.add('show');
                    btn.disabled = false;
                    btn.textContent = '重置密码';
                }}
            }} catch (err) {{
                errorEl.textContent = '网络错误，请稍后重试';
                errorEl.classList.add('show');
                btn.disabled = false;
                btn.textContent = '重置密码';
            }}
        }});
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html)

# 微信发布路由
from web.wechat_router import router as wechat_router
app.include_router(wechat_router)
logger.info("已启用微信发布路由（/api/wechat）")

# 封面图管理路由（上传 + AI 生成）
try:
    from web.cover_router import router as cover_router
    app.include_router(cover_router)
    logger.info("已启用封面图管理路由（/api/wechat/upload-cover, /api/wechat/generate-cover）")
except ImportError:
    logger.warning("封面图路由模块 web.cover_router 未找到，跳过")
except Exception as e:
    logger.warning(f"封面图路由加载失败: {e}，跳过")

# Jinja2 全局函数
def _formatTime(iso):
    if not iso:
        return '-'
    try:
        from datetime import datetime
        d = datetime.fromisoformat(str(iso))
        return d.strftime('%m-%d %H:%M')
    except Exception:
        return str(iso)[:16]

def _truncate(s, length=40):
    if not s:
        return ''
    return s[:length] + '...' if len(s) > length else s

jinja_env.globals['formatTime'] = _formatTime
jinja_env.globals['truncate'] = _truncate


def render_template(name: str, context: dict) -> HTMLResponse:
    """渲染 Jinja2 模板并返回 HTMLResponse（绕过 Starlette Jinja2Templates）"""
    template = jinja_env.get_template(name)
    html = template.render(**context)
    from fastapi.responses import Response as FastAPIResponse
    return FastAPIResponse(content=html, media_type="text/html",
                           headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                                    "Pragma": "no-cache",
                                    "Expires": "0"})
    return HTMLResponse(content=html)

# 存储
article_store = ArticleStore(data_dir=str(BASE_DIR.parent / "data"))
task_manager = TaskManager()
strategy_store = RewriteStrategyStore(db_path=str(BASE_DIR.parent / "data" / "content_aggregator.db"))

# WebSocket 连接池
ws_connections: list[WebSocket] = []
bg_scheduler: BackgroundScheduler | None = None

# 任务广播节流（防止 WebSocket 消息洪水）
ws_last_broadcast: dict[str, float] = {}  # task_id -> last broadcast timestamp (ms)
WS_BROADCAST_THROTTLE_MS = 500  # 相同任务最少间隔 500ms 广播一次


# ========================================================================
# 认证装饰器
# ========================================================================

async def require_auth(request: Request):
    """认证检查装饰器 - 需要登录才能访问"""
    if not AUTH_ENABLED:
        return {"user_id": 1, "username": "anonymous", "role": "user"}
    
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization Bearer Token")
    
    token = auth_header[7:]
    user_info = get_user_from_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    
    return user_info


async def broadcast_ws(message: dict):
    """广播消息到所有 WebSocket 客户端（带节流）"""
    task_id = message.get("task_id")
    now_ms = asyncio.get_event_loop().time() * 1000
    
    # 节流检查：相同 task_id 的消息至少间隔 WS_BROADCAST_THROTTLE_MS
    if task_id and task_id in ws_last_broadcast:
        if now_ms - ws_last_broadcast[task_id] < WS_BROADCAST_THROTTLE_MS:
            return  # 跳过此次广播（节流）
    
    ws_last_broadcast[task_id] = now_ms
    
    dead = []
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in ws_connections:
            ws_connections.remove(ws)


# ========================================================================
# 页面路由
# ========================================================================

@app.get("/", response_class=HTMLResponse)
async def page_index():
    """仪表盘"""
    sources_stats = article_store.get_sources()
    recent = article_store.get_all(page=1, per_page=10)

    # 数据源配置统计
    sources_config = CONFIG.get("sources", {})
    source_labels = {
        "rss": "RSS 订阅", "youtube": "YouTube", "twitter": "X (Twitter)",
        "tiktok": "TikTok", "douyin": "抖音", "douyin_hot": "抖音热点", "wangyi": "网易新闻",
        "weibo_hot": "微博热点", "xiaohongshu": "小红书", "wechat": "微信公众号",
        "sitemap": "Sitemap", "api": "自定义 API",
    }
    configured_count = 0  # 已配置（含启用+未启用）
    active_count = 0      # 活跃（当前启用的）
    configured_sources = []  # 模板列表展示用
    for src_type, src_cfg in sources_config.items():
        total = 0
        enabled = 0
        if isinstance(src_cfg, list):
            total = len(src_cfg)
            enabled = sum(1 for s in src_cfg if s.get("enabled", True))
        elif isinstance(src_cfg, dict):
            for list_key in ["channels", "users", "accounts", "sites", "endpoints"]:
                items = src_cfg.get(list_key, [])
                if items:
                    total = len(items)
                    # items 可能是字符串列表（如 sitemap sites），也可能是字典列表
                    enabled = sum(
                        1 for s in items
                        if isinstance(s, dict) and s.get("enabled", True) or isinstance(s, str)
                    )
                    break
            if total == 0 and (src_cfg.get("api_url") or src_cfg.get("base_url")):
                total = 1
                enabled = 1
        configured_count += total
        active_count += enabled
        configured_sources.append({
            "type": src_type,
            "label": source_labels.get(src_type, src_type),
            "count": enabled,
        })

    # 增强统计：改写数、今日采集数、总字数、来源分布
    all_articles = recent
    total_articles = all_articles['total']
    rewritten_count = 0
    today_count = 0
    total_words = 0
    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    source_dist = {}
    for src in sources_stats:
        # get_all per source to count
        src_arts = article_store.get_all(per_page=1, source=src['name'])
        source_dist[src['name']] = src['count'] if src.get('count') else src_arts.get('total', 0)
    # Iterate articles with pagination
    pg = 1
    while True:
        batch = article_store.get_all(page=pg, per_page=200)
        items = batch.get('items', batch.get('articles', []))
        if not items:
            break
        for a in items:
            total_words += len(a.get('content', '') or '')
            meta = a.get('metadata') or {}
            if meta.get('rewritten'):
                rewritten_count += 1
            ct = a.get('collected_at') or ''
            try:
                if ct and datetime.fromisoformat(ct.replace('Z', '+00:00')) >= today_start:
                    today_count += 1
            except:
                pass
        if len(items) < 200:
            break
        pg += 1

    return render_template("index.html", {
        "sources_stats": sources_stats,
        "recent_articles": recent["items"][:5],
        "total_articles": total_articles,
        "rewritten_count": rewritten_count,
        "today_count": today_count,
        "total_words": total_words,
        "source_dist": json.dumps(source_dist, ensure_ascii=False),
        "configured_sources": configured_sources,
        "configured_count": configured_count,
        "active_count": active_count,
        "tasks": task_manager.get_all()[-5:],
    })


@app.get("/articles", response_class=HTMLResponse)
async def page_articles(request: Request, page: int = 1, source: str | None = None):
    """文章列表"""
    result = article_store.get_all(page=page, per_page=20, source=source)
    sources = article_store.get_sources()
    return render_template("articles.html", {
        "request": request,
        "articles": result,
        "sources": sources,
        "current_source": source,
    })


@app.get("/articles/{article_id}", response_class=HTMLResponse)
async def page_article_detail(request: Request, article_id: str):
    """文章详情"""
    article = article_store.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return render_template("article_detail.html", {
        "request": request,
        "article": article,
    })


@app.get("/sources", response_class=HTMLResponse)
async def page_sources(request: Request):
    """数据源管理"""
    sources_config = CONFIG.get("sources", {})
    return render_template("sources.html", {
        "request": request,
        "sources_config": sources_config,
    })


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    """数据源配置（扩展平台）"""
    sources_config = CONFIG.get("sources", {})
    return render_template("settings.html", {
        "request": request,
        "config": {"sources": sources_config},
    })


@app.get("/compose", response_class=HTMLResponse)
async def page_compose(request: Request):
    """手动输入 → 改写 → 导出"""
    return render_template("compose.html", {
        "request": request,
    })


@app.get("/collect-link", response_class=HTMLResponse)
async def page_collect_link(request: Request):
    """链接采集页面"""
    return render_template("collect-link.html", {
        "request": request,
    })


@app.get("/tasks", response_class=HTMLResponse)
async def page_tasks(request: Request):
    """任务列表"""
    tasks = task_manager.get_all()
    return render_template("tasks.html", {
        "request": request,
        "tasks": reversed(tasks),
    })


@app.get("/system-settings", response_class=HTMLResponse)
async def page_system_settings(request: Request):
    """模型API设置（LLM、ASR、图片生成、Cookie）"""
    config = _migrate_config_models(load_config())
    # 确保所有配置section都有默认值，避免Jinja2模板报错
    for key in ["llm", "asr", "sources"]:
        if key not in config:
            config[key] = {}
    return render_template("system-settings.html", {
        "request": request,
        "config": config,
    })


@app.get("/wechat-settings", response_class=HTMLResponse)
async def page_wechat_settings(request: Request):
    """微信发布设置页面"""
    from wechat_publisher.theme import list_themes, load_theme
    cfg_path = os.path.join(os.path.dirname(__file__), "..", "config", "wechat_publish.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except:
        cfg = {"appid": "", "secret": "", "default_theme": "professional-clean"}
    names = list_themes()
    themes = []
    for name in names:
        try:
            t = load_theme(name)
            themes.append({"name": name, "display_name": t.name, "description": t.description})
        except:
            themes.append({"name": name, "display_name": name, "description": ""})
    return render_template("wechat_settings.html", {
        "request": request,
        "config": cfg,
        "themes": themes,
    })


# ========================================================================
# API 路由
# ========================================================================

# ========================================================================
# 设置 API
# ========================================================================

@app.get("/api/settings")
async def api_get_settings(request: Request):
    """读取当前配置（需要登录）"""
    user = await require_auth(request)
    config = _migrate_config_models(load_config())
    return {
        "llm": {
            "base_url": config.get("llm", {}).get("base_url", "http://127.0.0.1:19000/proxy/llm"),
            "model": config.get("llm", {}).get("model", "qclaw/pool-hy3-preview"),
            "api_key": config.get("llm", {}).get("api_key", ""),
            "models": config.get("llm", {}).get("models", []),
            "default_model_id": config.get("llm", {}).get("default_model_id", ""),
        },
        "asr": {
            "api_endpoint": config.get("asr", {}).get("api_endpoint", ""),
            "api_key": config.get("asr", {}).get("api_key", ""),
            "models": config.get("asr", {}).get("models", []),
        },
        "sources": {
            "xiaohongshu": {
                "cookie": config.get("sources", {}).get("xiaohongshu", {}).get("cookie", ""),
            }
        }
    }


@app.post("/api/settings")
async def api_save_settings(request: Request):
    """保存配置到 config.yaml（需要登录）"""
    user = await require_auth(request)
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 JSON 数据: {e}")

    # 验证 LLM API 端点格式
    llm_base_url = data.get("llm", {}).get("base_url", "")
    if llm_base_url and not llm_base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="LLM API 端点格式错误，必须以 http:// 或 https:// 开头")

    # 深度合并配置（保留其他配置项）
    config = load_config()
    
    # 更新 LLM 配置
    if "llm" in data:
        config["llm"] = {**config.get("llm", {}), **data["llm"]}
    
    # 更新 ASR 配置
    if "asr" in data:
        config["asr"] = {**config.get("asr", {}), **data["asr"]}
    
    # 更新 sources 配置
    if "sources" in data:
        if "sources" not in config:
            config["sources"] = {}
        if "xiaohongshu" in data["sources"]:
            if "xiaohongshu" not in config["sources"]:
                config["sources"]["xiaohongshu"] = {}
            config["sources"]["xiaohongshu"]["cookie"] = data["sources"]["xiaohongshu"].get("cookie", "")

    # 保存到 config.yaml
    if save_config(config):
        logger.info("[设置] 配置已保存")
        return {"status": "success", "message": "配置已保存"}
    else:
        raise HTTPException(status_code=500, detail="保存配置失败")


# ========================================================================
# 采集 API
# ========================================================================

@app.post("/api/collect/all")
async def api_collect_all(
    request: Request,
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发全源采集（后台任务，需要登录）"""
    user = await require_auth(request)
    task_id = task_manager.create("collect_all", "全源采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        async def progress_callback(current, total, message, progress):
            """进度回调函数：更新任务状态并广播 WebSocket 消息"""
            task_manager.update(task_id, status="running", progress=progress, message=message)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "running", "message": message, "progress": progress})

        try:
            task_manager.update(task_id, status="running", message="🔧 初始化流水线...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在初始化..."})

            async with ContentPipeline(CONFIG) as pipeline:
                result = await pipeline.process_all_sources(
                    rewrite=rewrite,
                    translate=bool(translate),
                    target_language=translate,
                    formats=fmt_list,
                    limit_per_source=limit,
                    progress_callback=progress_callback,  # 传递进度回调
                )

                # 存入 ArticleStore
                articles_objs = result.get("articles", [])
                logger.info(f"[DEBUG] 采集到文章数: {len(articles_objs)}")
                articles_data = [a.to_dict() for a in articles_objs]
                logger.info(f"[DEBUG] 转换为字典后文章数: {len(articles_data)}")
                added = article_store.add_batch(articles_data)
                logger.info(f"[DEBUG] 实际存储文章数: {added}, 存储后总数: {len(article_store.articles)}")
                # 提取 article_ids，供任务列表跳转使用（必须从 articles_data 取，因为 add_batch 会赋 ID）
                article_ids = [a["id"] for a in articles_data]

                summary = result.get("summary", {})
                msg = f"采集完成：{summary.get('success', 0)} 个源成功，{summary.get('total_articles', 0)} 篇文章"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary,
                    "article_ids": article_ids
                })
                # 广播完整任务信息（包含 result, started_at, finished_at）
                task = task_manager.get(task_id)
                await broadcast_ws({
                    "type": "task_update",
                    "task_id": task_id,
                    "status": task["status"],
                    "message": task["message"],
                    "progress": task["progress"],
                    "result": task.get("result"),
                    "start_time": task.get("started_at"),
                    "end_time": task.get("finished_at")
                })

        except Exception as e:
            error_msg = f"采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            # 广播完整任务信息（包含 finished_at）
            task = task_manager.get(task_id)
            await broadcast_ws({
                "type": "task_update",
                "task_id": task_id,
                "status": task["status"],
                "message": task["message"],
                "progress": task["progress"],
                "result": task.get("result"),
                "start_time": task.get("started_at"),
                "end_time": task.get("finished_at")
            })
            logger.error(error_msg, exc_info=True)

    # 注册 asyncio.Task 到 TaskManager（支持取消）
    async_task = asyncio.create_task(run_task())
    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


# YouTube 采集

@app.post("/api/collect/youtube")
async def api_collect_youtube(
    request: Request,
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发 YouTube 采集（后台任务，需要登录）"""
    user = await require_auth(request)
    task_id = task_manager.create("collect_youtube", "YouTube 采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        # YouTube 采集的进度回调（单源，进度 0-100）
        async def progress_callback(current, total, message, progress):
            task_manager.update(task_id, status="running", progress=progress, message=message)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "running", "message": message, "progress": progress})

        try:
            task_manager.update(task_id, status="running", message="📡 正在采集 YouTube...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "📡 正在采集 YouTube..."})

            async with ContentPipeline(CONFIG) as pipeline:
                # 只采集 YouTube 源
                result = await pipeline.process_source("youtube",
                    rewrite=rewrite,
                    translate=bool(translate),
                    target_language=translate,
                    formats=fmt_list,
                    limit_per_source=limit,
                    progress_callback=progress_callback,  # 传递进度回调
                )

                articles_objs = result.get("articles", [])
                articles_data = [a.to_dict() for a in articles_objs]
                added = article_store.add_batch(articles_data)
                # 必须从 articles_data 取 ID（add_batch 会赋 ID，但不会影响 articles_objs）
                article_ids = [a["id"] for a in articles_data]

                summary = result.get("summary", {})
                msg = f"YouTube 采集完成：{summary.get('success', 0)} 个任务成功，{summary.get('total_articles', 0)} 篇"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary,
                    "article_ids": article_ids
                })
                # 广播完整任务信息（包含 result, started_at, finished_at）
                task = task_manager.get(task_id)
                await broadcast_ws({
                    "type": "task_update",
                    "task_id": task_id,
                    "status": task["status"],
                    "message": task["message"],
                    "progress": task["progress"],
                    "result": task.get("result"),
                    "start_time": task.get("started_at"),
                    "end_time": task.get("finished_at")
                })

        except Exception as e:
            error_msg = f"YouTube 采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            # 广播完整任务信息（包含 finished_at）
            task = task_manager.get(task_id)
            await broadcast_ws({
                "type": "task_update",
                "task_id": task_id,
                "status": task["status"],
                "message": task["message"],
                "progress": task["progress"],
                "result": task.get("result"),
                "start_time": task.get("started_at"),
                "end_time": task.get("finished_at")
            })
            logger.error(error_msg, exc_info=True)

    # 注册 asyncio.Task 到 TaskManager（支持取消）
    async_task = asyncio.create_task(run_task())
    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/collect/url")
async def api_collect_url(
    request: Request,
    url: str = Form(...),
    rewrite: bool = Form(default=True),
    strategy: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """采集单个 URL（需要登录）"""
    user = await require_auth(request)
    task_id = task_manager.create("collect_url", f"采集: {url[:50]}")

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="📡 正在采集...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "📡 正在采集..."})

            fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]
            async with ContentPipeline(CONFIG) as pipeline:
                # Map strategy string to RewriteStrategy enum
                strat = None
                if strategy:
                    from content_aggregator.processors.rewrite import RewriteStrategy
                    strategy_map = {
                        'REWRITE': RewriteStrategy.REWRITE,
                        'PARAPHRASE': RewriteStrategy.PARAPHRASE,
                        'STYLE_TRANSFER': RewriteStrategy.STYLE_TRANSFER,
                        'SUMMARIZE': RewriteStrategy.SUMMARIZE,
                        'EXPAND': RewriteStrategy.EXPAND,
                        'rewrite': RewriteStrategy.REWRITE,
                        'paraphrase': RewriteStrategy.PARAPHRASE,
                        'style_transfer': RewriteStrategy.STYLE_TRANSFER,
                        'summarize': RewriteStrategy.SUMMARIZE,
                        'expand': RewriteStrategy.EXPAND,
                    }
                    strat = strategy_map.get(strategy)
                articles = await pipeline.process_url(url, rewrite=rewrite, strategy=strat, limit=limit)

                if articles:
                    added = article_store.add_batch([a.to_dict() for a in articles])
                    for a in articles:
                        for fmt in fmt_list:
                            try:
                                pipeline.exporter.export(a, fmt)
                            except Exception as e:
                                logger.warning(f"导出失败 ({fmt}): {e}")

                    msg = f"采集成功: {added}/{len(articles)} 篇" + (f"（{len(articles)-added}篇重复跳过）" if added < len(articles) else "")
                    task_manager.update(task_id, status="done", progress=100,
                                        message=msg,
                                        result={"count": added, "total": len(articles), "article_ids": [a.id for a in articles[:added]]})
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "done", "message": f"成功 采集 {len(articles)} 篇"})
                else:
                    task_manager.update(task_id, status="error", message="采集失败：无内容")
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "error", "message": "采集失败"})

        except Exception as e:
            error_msg = f"采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/collect-link")
async def api_collect_link(
    request: Request,
    url: str = Form(...),
    platform: str = Form(default="auto"),
):
    """
    链接采集 API：解析小红书/抖音链接，返回文案内容（需要登录）
    """
    user = await require_auth(request)
    task_id = task_manager.create("collect_link", f"采集链接: {url[:50]}")

    async def run_task():
        nonlocal platform  # 允许内部函数修改外部函数的 platform 参数
        try:
            task_manager.update(task_id, status="running", message="🔍 正在识别平台...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "🔍 正在识别平台..."})

            # 1. 平台识别
            if platform == "auto":
                from content_aggregator.sources.collectors.xiaohongshu_collector import XiaohongshuCollector
                from content_aggregator.sources.collectors.douyin_collector import DouyinCollector
                if XiaohongshuCollector.detect_platform(url):
                    platform = "xiaohongshu"
                elif DouyinCollector.detect_platform(url):
                    platform = "douyin"
                else:
                    raise ValueError("无法识别链接平台，请手动选择")

            # 2. 调用对应采集器
            task_manager.update(task_id, status="running", progress=30, message=f"🔍 正在采集 {platform} 内容...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "progress": 30, "message": f"🔍 正在采集 {platform} 内容..."})

            config = load_config()
            if platform == "xiaohongshu":
                collector = XiaohongshuCollector(
                    cookie=config.get("sources", {}).get("xiaohongshu", {}).get("cookie"),
                    xhs_token=config.get("sources", {}).get("xiaohongshu", {}).get("xhs_token"),
                )
            elif platform == "douyin":
                collector = DouyinCollector(
                    cookie=config.get("sources", {}).get("douyin", {}).get("cookie"),
                    client_key=config.get("sources", {}).get("douyin", {}).get("client_key"),
                )
            else:
                raise ValueError(f"不支持的平台: {platform}")

            result = await collector.fetch_by_url(url)

            # 3. 如果有视频，尝试 ASR 转写
            if result.get("media_type") == "video" and result.get("metadata", {}).get("video_url"):
                video_url = result["metadata"]["video_url"]
                task_manager.update(task_id, status="running", progress=60, message=f"🎬 正在下载音频（{video_url[:40]}...）")
                await broadcast_ws({
                    "type": "task_update",
                    "task_id": task_id,
                    "status": "running",
                    "progress": 60,
                    "message": "🎬 正在下载音频...",
                })

                # 构建 ASR 配置（从系统设置读取）
                asr_models = config.get("asr", {}).get("models", [])
                if asr_models:
                    # 取第一个模型作为默认
                    asr_model = asr_models[0]
                    asr_cfg = ASRConfig(
                        api_endpoint=asr_model.get("base_url", ""),
                        api_key=asr_model.get("api_key", ""),
                        model_id=asr_model.get("model_id", "whisper-1"),
                    )
                    if asr_cfg.api_endpoint:
                        try:
                            from content_aggregator.processors.asr_processor import ASRProcessor

                            async with ASRProcessor(asr_cfg) as asr:
                                asr_result = await asr.process(
                                    video_url,
                                    progress_callback=lambda c, t, m: task_manager.update(
                                        task_id, status="running", progress=60 + int(c * 0.4), message=m
                                    ),
                                )
                                if asr_result.success:
                                    result["transcribed_text"] = asr_result.transcribed_text
                                    logger.info(
                                        f"ASR 转写成功: {asr_result.word_count}字, "
                                        f"耗时{asr_result.duration:.1f}s"
                                    )
                                    await broadcast_ws({
                                        "type": "task_update",
                                        "task_id": task_id,
                                        "status": "running",
                                        "progress": 90,
                                        "message": f"ASR 转写完成: {asr_result.word_count}字",
                                    })
                                else:
                                    logger.warning(f"ASR 转写失败: {asr_result.error}")
                                    result["transcribed_text"] = f"[ASR 转写失败: {asr_result.error}]"
                        except Exception as e:
                            logger.error(f"ASR 处理异常: {e}")
                            result["transcribed_text"] = f"[ASR 处理异常: {e}]"
                    else:
                        logger.info("ASR API 端点未配置，跳过转写")
                        result["transcribed_text"] = ""
                else:
                    logger.info("未配置 ASR 模型，跳过转写")
                    result["transcribed_text"] = ""

            # 4. 保存到 article_store
            article_data = {
                "id": str(uuid.uuid4()),
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "url": result.get("url", url),
                "author": result.get("author", ""),
                "published_at": result.get("published_at"),
                "summary": result.get("summary", ""),
                "tags": result.get("tags", []),
                "source": result.get("source", platform),
                "media_type": result.get("media_type", "text"),
                "original_text": result.get("original_text", ""),
                "transcribed_text": result.get("transcribed_text", ""),
                "created_at": datetime.now().isoformat(),
                "metadata": result.get("metadata", {}),
            }
            article_store.add(article_data)

            task_manager.update(task_id, status="done", progress=100,
                              message=f"采集成功: {result.get('title', '')[:30]}",
                              result={"article_id": article_data["id"], "platform": platform})
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "done", "progress": 100, "message": "采集成功"})

        except Exception as e:
            error_msg = f"采集失败: {e}"
            logger.error(error_msg)
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/rewrite")
async def api_rewrite(
    request: Request,
    article_id: str = Form(...),
    strategy: str = Form(default="REWRITE"),
    translate: str = Form(default="no"),
    industry: str = Form(default=""),
):
    """改写已有文章（带进度反馈，需要登录）"""
    user = await require_auth(request)
    article = article_store.get_by_id(article_id)
    if not article:
        return JSONResponse({"success": False, "error": "文章不存在"})

    task_id = task_manager.create("rewrite", f"改写: {article.get('title', '')[:30]}")

    async def run_task():
        try:
            # 进度回调：改写是单篇，用 0% → 50%（调用LLM）→ 100%（完成）
            async def progress_callback(current, total, message, progress):
                task_manager.update(task_id, status="running", progress=progress, message=message)
                await broadcast_ws({"type": "task_update", "task_id": task_id,
                                            "status": "running", "message": message, "progress": progress})

            task_manager.update(task_id, status="running", message="✍️ 正在改写...", progress=0)

            from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
            async with RewriteProcessor(CONFIG) as processor:
                content = Content(
                    id=article.get("id", ""),
                    source_id=article.get("source", ""),
                    source_type="web",
                    url=article.get("source_url", ""),
                    title=article.get("title", ""),
                    content=article.get("content", ""),
                )
                strategy_map = {
                    'REWRITE': RewriteStrategy.REWRITE,
                    'PARAPHRASE': RewriteStrategy.PARAPHRASE,
                    'STYLE_TRANSFER': RewriteStrategy.STYLE_TRANSFER,
                    'SUMMARIZE': RewriteStrategy.SUMMARIZE,
                    'EXPAND': RewriteStrategy.EXPAND,
                }
                cfg_strategy = strategy_map.get(strategy, RewriteStrategy.REWRITE)

                # 语言检测：translate=yes 时自动识别原文语言
                source_lang = None
                source_lang_name = None
                if translate == "yes":
                    from content_aggregator.processors.language_detector import LanguageDetector
                    detector = LanguageDetector(CONFIG.get("llm", {}))
                    lang_result = await detector.detect(
                        article.get("content", ""), article.get("title", "")
                    )
                    source_lang = lang_result.language
                    source_lang_name = lang_result.language_name

                config = RewriteConfig(
                    strategy=cfg_strategy,
                    translate_to="zh" if translate == "yes" else None,
                    source_language=source_lang,
                    source_language_name=source_lang_name,
                    industry=industry.strip() if industry else None,
                )
                # 调用改写，并传递进度回调
                result = await processor.rewrite(content, config, progress_callback=progress_callback)

                if result.success:
                    original_text = article.get("content", "")
                    original_title_text = article.get("title", "")
                    article["original_content"] = original_text
                    article["original_title"] = original_title_text
                    article["title"] = result.title or original_title_text
                    article["content"] = result.rewritten_content
                    article["word_count"] = len(result.rewritten_content)
                    article["summary"] = result.summary
                    if "metadata" not in article:
                        article["metadata"] = {}
                    article["metadata"]["rewritten"] = True
                    article["metadata"]["rewrite_strategy"] = config.strategy.value
                    article["metadata"]["translate_to"] = config.translate_to
                    article["metadata"]["original_content"] = original_text
                    # 语言检测结果（手动触发改写也记录）
                    if source_lang:
                        article["metadata"]["language_detected"] = source_lang
                        article["metadata"]["language_name"] = source_lang_name or source_lang
                        article["metadata"]["translated_before_rewrite"] = True
                    article_store.save()

                    task_manager.update(task_id, status="done", progress=100,
                                        message="改写完成", result={"article_id": article_id})
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "done", "message": "改写完成", "article_id": article_id})
                else:
                    task_manager.update(task_id, status="error", message=f"改写失败: {result.error}")

        except Exception as e:
            task_manager.update(task_id, status="error", message=f"改写失败: {e}")

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


# ========================================================================
# 策略管理 API
# ========================================================================

BUILTIN_STRATEGIES = [
    {"id": "REWRITE", "name": "\u6df1\u5ea6\u6539\u5199", "description": "\u5168\u9762\u6539\u5199\u6587\u7ae0\u5185\u5bb9\u548c\u7ed3\u6784\uff0c\u4fdd\u6301\u6838\u5fc3\u4fe1\u606f", "is_builtin": True},
    {"id": "PARAPHRASE", "name": "\u540c\u4e49\u6539\u5199", "description": "\u7528\u4e0d\u540c\u8868\u8fbe\u91cd\u5199\u539f\u6587\uff0c\u4fdd\u6301\u539f\u610f", "is_builtin": True},
    {"id": "STYLE_TRANSFER", "name": "\u98ce\u683c\u8f6c\u6362", "description": "\u5c06\u6587\u7ae0\u8f6c\u6362\u4e3a\u4e0d\u540c\u98ce\u683c\uff08\u5982\u5b66\u672f\u3001\u53e3\u8bed\u7b49\uff09", "is_builtin": True},
    {"id": "SUMMARIZE", "name": "\u6458\u8981\u7cbe\u7b80", "description": "\u63d0\u70bc\u6587\u7ae0\u6838\u5fc3\u89c2\u70b9\uff0c\u751f\u6210\u7b80\u6d01\u6458\u8981", "is_builtin": True},
    {"id": "EXPAND", "name": "\u6269\u5c55\u5199\u4f5c", "description": "\u5728\u539f\u6587\u57fa\u7840\u4e0a\u6269\u5c55\u5185\u5bb9\uff0c\u589e\u52a0\u7ec6\u8282\u548c\u4e3e\u4f8b", "is_builtin": True},
    {"id": "FORMAL", "name": "\u6b63\u5f0f\u4e13\u4e1a", "description": "\u5c06\u6587\u7ae0\u6539\u5199\u4e3a\u6b63\u5f0f\u3001\u4e13\u4e1a\u7684\u8868\u8fbe\u98ce\u683c", "is_builtin": True},
]


@app.get("/api/rewrite-strategies")
async def api_get_strategies(request: Request):
    """获取策略列表（内置 + 自定义，需要登录）"""
    user = await require_auth(request)
    custom = strategy_store.get_all()
    # \u6807\u8bb0\u81ea\u5b9a\u4e49\u7b56\u7565
    for s in custom:
        s["is_builtin"] = False
    default_strategy = strategy_store.get_default()
    default_id = default_strategy["id"] if default_strategy else None
    return JSONResponse({
        "success": True,
        "builtin": BUILTIN_STRATEGIES,
        "custom": custom,
        "default_id": default_id,
    })


@app.post("/api/rewrite-strategies")
async def api_create_strategy(request: Request):
    """新建自定义策略（需要登录）"""
    user = await require_auth(request)
    data = await request.json()
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    is_default = data.get("is_default", False)

    if not name or not description:
        return JSONResponse({"success": False, "error": "\u540d\u79f0\u548c\u63cf\u8ff0\u4e0d\u80fd\u4e3a\u7a7a"}, status_code=400)

    try:
        strategy = strategy_store.create(name=name, description=description, is_default=is_default)
        return JSONResponse({"success": True, "strategy": strategy})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.patch("/api/rewrite-strategies/{strategy_id}")
async def api_update_strategy(strategy_id: str, request: Request):
    """\u66f4\u65b0\u7b56\u7565"""
    data = await request.json()
    try:
        result = strategy_store.update(
            strategy_id=strategy_id,
            name=data.get("name"),
            description=data.get("description"),
            is_default=data.get("is_default"),
        )
        if result is None:
            return JSONResponse({"success": False, "error": "\u7b56\u7565\u4e0d\u5b58\u5728"}, status_code=404)
        return JSONResponse({"success": True, "strategy": result})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.delete("/api/rewrite-strategies/{strategy_id}")
async def api_delete_strategy(strategy_id: str, request: Request):
    """\u5220\u9664\u7b56\u7565（需要登录）"""
    user = await require_auth(request)
    try:
        deleted = strategy_store.delete(strategy_id)
        if not deleted:
            return JSONResponse({"success": False, "error": "\u7b56\u7565\u4e0d\u5b58\u5728"}, status_code=404)
        return JSONResponse({"success": True})
    except ValueError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/rewrite-strategies", response_class=HTMLResponse)
async def page_rewrite_strategies(request: Request):
    """\u7b56\u7565\u7ba1\u7406\u9875\u9762"""
    return render_template("rewrite-strategies.html", {
        "request": request,
    })


@app.post("/api/compose")
async def api_compose(
    request: Request,
    title: str = Form(default=""),
    content: str = Form(...),
    action: str = Form(default="export"),
    format_type: str = Form(default="markdown"),
    strategy: str = Form(default="REWRITE"),
    translate: str = Form(default="no"),
):
    """手动输入内容 → 改写/导出（需要登录）"""
    user = await require_auth(request)
    task_id = task_manager.create("compose", f"处理: {title[:30] if title else '手动输入'}")

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="🔧 正在处理...")

            from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
            from content_aggregator.exporters import Exporter

            rewritten_content = content
            current_title = title  # avoid UnboundLocalError from assignment in rewrite branch
            if action == "rewrite":
                async with RewriteProcessor(CONFIG) as processor:
                    c = Content(
                        id=str(__import__("uuid").uuid4()),
                        source_id="manual",
                        source_type="manual",
                        title=title,
                        content=content,
                    )
                    strategy_map = {
                        'REWRITE': RewriteStrategy.REWRITE,
                        'PARAPHRASE': RewriteStrategy.PARAPHRASE,
                        'STYLE_TRANSFER': RewriteStrategy.STYLE_TRANSFER,
                        'SUMMARIZE': RewriteStrategy.SUMMARIZE,
                        'EXPAND': RewriteStrategy.EXPAND,
                    }
                    cfg = RewriteConfig(
                        strategy=strategy_map.get(strategy, RewriteStrategy.REWRITE),
                        translate_to="zh" if translate == "yes" else None,
                    )
                    result = await processor.rewrite(c, cfg)
                    if result.success:
                        rewritten_content = result.rewritten_content
                        current_title = result.title or title
                    else:
                        task_manager.update(task_id, status="error", message=f"改写失败: {result.error}")
                        return

            # 导出
            article_data = {
                "id": str(__import__("uuid").uuid4()),
                "title": current_title or "手动输入",
                "content": rewritten_content,
                "word_count": len(rewritten_content),
                "source_type": "manual",
                "source_url": f"manual:{str(uuid.uuid4())}",
            }
            # 改写模式下保存原文供对照
            if action == "rewrite":
                article_data["original_content"] = content
                article_data["original_title"] = title or ""
                article_data["metadata"] = {
                    "rewritten": True,
                    "rewrite_strategy": strategy,
                    "original_content": content,
                }
            article_store.add(article_data)

            from content_aggregator.models import Article
            article_obj = Article(
                id=article_data["id"],
                title=article_data.get("title", ""),
                original_title=article_data.get("original_title", ""),
                content=article_data.get("content", ""),
                source=article_data.get("source", "manual"),
                source_url=article_data.get("source_url", ""),
                author=article_data.get("author", ""),
                summary=article_data.get("summary", ""),
                tags=article_data.get("tags", []),
                word_count=article_data.get("word_count", 0),
                metadata=article_data.get("metadata", {}),
            )
            aid = article_data["id"]
            output_dir = CONFIG.get("export", {}).get("output_dir", "./output/exports")
            exporter = Exporter(output_dir)
            path = exporter.export(article_obj, format_type)

            task_manager.update(task_id, status="done", progress=100,
                                message=f"处理完成: {current_title}", result={"path": str(path), "article_id": aid})
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "done", "message": f"处理完成", "article_id": aid})

        except Exception as e:
            task_manager.update(task_id, status="error", message=f"处理失败: {e}")

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.get("/api/articles")
async def api_list_articles(
    request: Request,
    page: int = 1,
    per_page: int = 50,
    source: str | None = None,
):
    """获取文章列表（需要登录）"""
    user = await require_auth(request)
    result = article_store.get_all(page=page, per_page=per_page, source=source)
    sources = article_store.get_sources()
    return JSONResponse({
        "articles": result.get("items", []),
        "total": result.get("total", 0),
        "page": page,
        "per_page": per_page,
        "total_pages": result.get("pages", 1),
        "sources": sources,
    })


@app.get("/api/articles/{article_id}")
async def api_get_article(article_id: str, request: Request):
    """获取单篇文章（需要登录）"""
    user = await require_auth(request)
    article = article_store.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return JSONResponse(article)


@app.delete("/api/articles/{article_id}")
async def api_delete_article(article_id: str, request: Request):
    """删除文章（需要登录）"""
    user = await require_auth(request)
    if article_store.delete(article_id):
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "文章不存在"})


@app.post("/api/export/pdf")
async def api_export_pdf(request: Request):
    """导出文章为 PDF（需要登录）"""
    user = await require_auth(request)
    try:
        body = await request.json()
        from content_aggregator.models import Article as ArticleModel
        from content_aggregator.exporters import PDFExporter
        art = ArticleModel.from_dict(body)
        exp = PDFExporter()
        safe_title = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in art.title)[:50]
        out_path = os.path.join(tempfile.gettempdir(), f"{safe_title}.pdf")
        result = exp.export(art, out_path)
        if not result.success:
            raise RuntimeError(result.error)
        return FileResponse(out_path, media_type="application/pdf", filename="article.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/articles/clear")
async def api_clear_articles(request: Request):
    """清空文章（需要登录）"""
    user = await require_auth(request)
    article_store.clear()
    return JSONResponse({"success": True})


@app.post("/api/cache/clear")
async def api_clear_cache(request: Request):
    """清空缓存（需要登录）"""
    user = await require_auth(request)
    try:
        # 调用 DedupFilter.reset() 方法
        if pipeline and hasattr(pipeline, 'dedup_filter'):
            pipeline.dedup_filter.reset()
            logger.info("[Cache] 去重缓存已清除（调用 reset() 方法）")
        else:
            # 备用方案：直接删除文件
            import os
            cache_file = "data/dedup_cache.json"
            if os.path.exists(cache_file):
                os.remove(cache_file)
                logger.info("[Cache] 缓存文件已删除（备用方案）")
        
        return JSONResponse({"success": True, "message": "去重缓存已清除"})
    except Exception as e:
        logger.error(f"[Cache] 清除缓存失败: {e}")
        return JSONResponse({"success": False, "error": str(e)})


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str, request: Request):
    """查询任务状态（需要登录）"""
    user = await require_auth(request)
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JSONResponse(task)


@app.get("/api/tasks")
async def api_list_tasks(request: Request):
    """获取任务列表（需要登录）"""
    user = await require_auth(request)
    return JSONResponse(task_manager.get_all())


@app.delete("/api/tasks/{task_id}")
async def api_cancel_task(task_id: str, request: Request):
    """取消任务（需要登录）"""
    user = await require_auth(request)
    success = task_manager.cancel(task_id)
    if not success:
        task = task_manager.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        else:
            raise HTTPException(status_code=400, detail=f"任务状态为 {task['status']}，无法取消")
    return JSONResponse({"success": True, "message": "任务已取消"})


@app.post("/api/tasks/{task_id}/cancel")
async def api_cancel_task_post(task_id: str, request: Request):
    """取消任务（POST 版本，兼容表单提交）"""
    user = await require_auth(request)
    success = task_manager.cancel(task_id)
    if not success:
        task = task_manager.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        else:
            raise HTTPException(status_code=400, detail=f"任务状态为 {task['status']}，无法取消")
    return JSONResponse({"success": True, "message": "任务已取消"})


@app.get("/api/sources")
async def api_list_sources(request: Request):
    """获取数据源列表（需要登录）"""
    user = await require_auth(request)
    sources = CONFIG.get("sources", {})
    result = {}
    for src_type, src_cfg in sources.items():
        if isinstance(src_cfg, list):
            result[src_type] = [
                {"name": s.get("name", "") if isinstance(s, dict) else str(s),
                 "enabled": s.get("enabled", True) if isinstance(s, dict) else True}
                for s in src_cfg
            ]
        elif isinstance(src_cfg, dict):
            entries = []
            for list_key in ["channels", "users", "accounts", "sites", "endpoints"]:
                for s in src_cfg.get(list_key, []):
                    if isinstance(s, dict):
                        entries.append({"name": s.get("name", ""), "enabled": s.get("enabled", True)})
                    else:
                        # Handle string items (e.g., youtube channel IDs, sitemap URLs)
                        entries.append({"name": str(s), "enabled": True})
            result[src_type] = entries
    return JSONResponse(result)


@app.post("/api/sources/rss")
async def api_add_rss_source(request: Request, name: str = Form(...), url: str = Form(...), enabled: str = Form(default="on")):
    """添加 RSS 源（需要登录）"""
    user = await require_auth(request)
    global CONFIG
    if "rss" not in CONFIG.get("sources", {}):
        CONFIG.setdefault("sources", {})["rss"] = []
    rss_list = CONFIG["sources"]["rss"]
    # Check duplicate URL
    for s in rss_list:
        if s.get("url") == url:
            return JSONResponse({"success": False, "error": "该 URL 已存在"})
    rss_list.append({"name": name, "url": url, "enabled": enabled == "on"})
    if save_config(CONFIG):
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "保存失败"})


@app.delete("/api/sources/rss/{name}")
async def api_delete_rss_source(name: str, request: Request):
    """删除 RSS 数据源（需要登录）"""
    user = await require_auth(request)
    global CONFIG
    rss_list = CONFIG.get("sources", {}).get("rss", [])
    original_len = len(rss_list)
    CONFIG["sources"]["rss"] = [s for s in rss_list if s.get("name") != name]
    if len(CONFIG["sources"]["rss"]) < original_len:
        if save_config(CONFIG):
            return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "未找到该源"})


@app.post("/api/sources/rss/{name}/toggle")
async def api_toggle_rss_source(name: str, request: Request):
    """启用/禁用 RSS 数据源（需要登录）"""
    user = await require_auth(request)
    global CONFIG
    for s in CONFIG.get("sources", {}).get("rss", []):
        if s.get("name") == name:
            s["enabled"] = not s.get("enabled", True)
            if save_config(CONFIG):
                return JSONResponse({"success": True, "enabled": s["enabled"]})
    return JSONResponse({"success": False, "error": "未找到该源"})


# ========================================================================
# 热点源启用/禁用 API（单配置源：douyin_hot, wangyi, weibo_hot）
# ========================================================================

_HOT_SOURCE_TYPES = {"douyin_hot", "wangyi", "weibo_hot"}


@app.post("/api/sources/hot/{source_type}/toggle")
async def api_toggle_hot_source(request: Request, source_type: str):
    """切换热文源（需要登录）"""
    user = await require_auth(request)
    if source_type not in _HOT_SOURCE_TYPES:
        return JSONResponse({"success": False, "error": f"不支持的源类型: {source_type}"})
    global CONFIG
    src_cfg = CONFIG.get("sources", {}).get(source_type)
    if not src_cfg:
        return JSONResponse({"success": False, "error": f"未配置 {source_type}"})
    src_cfg["enabled"] = not src_cfg.get("enabled", True)
    if save_config(CONFIG):
        return JSONResponse({"success": True, "enabled": src_cfg["enabled"]})
    return JSONResponse({"success": False, "error": "保存失败"})


# ========================================================================
# 单源采集 API（热点源）
# ========================================================================

_SOURCE_LABELS = {
    "douyin_hot": "抖音热点榜",
    "wangyi": "网易新闻",
    "weibo_hot": "微博热点",
}


@app.post("/api/collect/douyin_hot")
async def api_collect_douyin_hot(
    request: Request,
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发抖音热点榜采集（需要登录）"""
    user = await require_auth(request)
    task_id = task_manager.create("collect_douyin_hot", "抖音热点榜采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        async def progress_callback(current, total, message, progress):
            task_manager.update(task_id, status="running", progress=progress, message=message)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "running", "message": message, "progress": progress})

        try:
            task_manager.update(task_id, status="running", message="正在采集抖音热点榜...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在采集抖音热点榜..."})

            async with ContentPipeline(CONFIG) as pipeline:
                result = await pipeline.process_source(
                    "douyin_hot",
                    rewrite=rewrite, translate=bool(translate),
                    target_language=translate, formats=fmt_list,
                    limit_per_source=limit, progress_callback=progress_callback,
                )
                articles_data = [a.to_dict() for a in result.get("articles", [])]
                article_store.add_batch(articles_data)
                article_ids = [a.id for a in result.get("articles", [])]
                summary = result.get("summary", {})
                msg = f"抖音热点榜采集完成：{summary.get('total_articles', 0)} 条"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary, "article_ids": article_ids
                })
                await broadcast_ws({"type": "task_update", "task_id": task_id,
                                    "status": "done", "message": msg})
        except Exception as e:
            error_msg = f"抖音热点榜采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})
            logger.error(error_msg, exc_info=True)

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/collect/wangyi")
async def api_collect_wangyi(
    request: Request,
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发网易新闻采集（需要登录）"""
    # DEBUG: 打印请求头帮助定位 422
    ct = request.headers.get("content-type", "NONE")
    logger.warning(f"[DEBUG] wangyi collect content-type={ct}")
    user = await require_auth(request)
    task_id = task_manager.create("collect_wangyi", "网易新闻采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        async def progress_callback(current, total, message, progress):
            task_manager.update(task_id, status="running", progress=progress, message=message)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "running", "message": message, "progress": progress})

        try:
            task_manager.update(task_id, status="running", message="正在采集网易新闻...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在采集网易新闻..."})

            async with ContentPipeline(CONFIG) as pipeline:
                result = await pipeline.process_source(
                    "wangyi",
                    rewrite=rewrite, translate=bool(translate),
                    target_language=translate, formats=fmt_list,
                    limit_per_source=limit, progress_callback=progress_callback,
                )
                articles_data = [a.to_dict() for a in result.get("articles", [])]
                article_store.add_batch(articles_data)
                article_ids = [a.id for a in result.get("articles", [])]
                summary = result.get("summary", {})
                msg = f"网易新闻采集完成：{summary.get('total_articles', 0)} 篇"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary, "article_ids": article_ids
                })
                await broadcast_ws({"type": "task_update", "task_id": task_id,
                                    "status": "done", "message": msg})
        except Exception as e:
            error_msg = f"网易新闻采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})
            logger.error(error_msg, exc_info=True)

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/collect/weibo_hot")
async def api_collect_weibo_hot(
    request: Request,
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发微博热点采集（需要登录）"""
    user = await require_auth(request)
    task_id = task_manager.create("collect_weibo_hot", "微博热点采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        async def progress_callback(current, total, message, progress):
            task_manager.update(task_id, status="running", progress=progress, message=message)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "running", "message": message, "progress": progress})

        try:
            task_manager.update(task_id, status="running", message="正在采集微博热点...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在采集微博热点..."})

            async with ContentPipeline(CONFIG) as pipeline:
                result = await pipeline.process_source(
                    "weibo_hot",
                    rewrite=rewrite, translate=bool(translate),
                    target_language=translate, formats=fmt_list,
                    limit_per_source=limit, progress_callback=progress_callback,
                )
                articles_data = [a.to_dict() for a in result.get("articles", [])]
                article_store.add_batch(articles_data)
                article_ids = [a.id for a in result.get("articles", [])]
                summary = result.get("summary", {})
                msg = f"微博热点采集完成：{summary.get('total_articles', 0)} 条"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary, "article_ids": article_ids
                })
                await broadcast_ws({"type": "task_update", "task_id": task_id,
                                    "status": "done", "message": msg})
        except Exception as e:
            error_msg = f"微博热点采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})
            logger.error(error_msg, exc_info=True)

    # 注册 asyncio.Task 到 TaskManager（支持取消）


    async_task = asyncio.create_task(run_task())


    task_manager.register_async_task(task_id, async_task)
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.get("/api/config")
async def api_get_config(request: Request):
    """读取配置（需要登录）"""
    user = await require_auth(request)
    safe_config = json.loads(json.dumps(CONFIG))
    # 脱敏
    def mask_keys(obj, keys=("api_key", "bearer_token", "session_id", "cookie", "xhs_token", "client_key")):
        if isinstance(obj, dict):
            for k in keys:
                if k in obj and obj[k]:
                    obj[k] = "***" if len(str(obj[k])) > 4 else obj[k]
            for v in obj.values():
                mask_keys(v, keys)
        elif isinstance(obj, list):
            for item in obj:
                mask_keys(item, keys)
    mask_keys(safe_config)
    return JSONResponse(safe_config)


@app.put("/api/config")
async def api_update_config(request: Request):
    """更新配置（需要登录）"""
    user = await require_auth(request)
    global CONFIG
    try:
        body = await request.json()
        if "sources" in body:
            if "sources" not in CONFIG:
                CONFIG["sources"] = {}
            for key, value in body["sources"].items():
                if isinstance(value, dict) and isinstance(CONFIG["sources"].get(key), dict):
                    # 深度合并：只跳过 null（保留前端未传递的字段）
                    # 注意：空列表 [] 和空字符串 "" 需要保存（用户主动清空）
                    for fk, fv in value.items():
                        if fv is not None:  # ✅ 修复：允许空列表和空字符串
                            CONFIG["sources"][key][fk] = fv
                elif value is not None:
                    CONFIG["sources"][key] = value
        if save_config(CONFIG):
            return JSONResponse({"success": True})
        else:
            # save_config 返回 False，记录详细错误
            logger.error(f"[Config] save_config returned False for CONFIG keys: {list(CONFIG.keys())}")
            return JSONResponse({"success": False, "error": "保存失败，请检查服务器日志"})
    except Exception as e:
        import traceback
        logger.error(f"Config save error: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse({"success": False, "error": f"保存失败: {str(e)[:200]}"})


@app.get("/api/stats")
async def api_stats(request: Request):
    """获取统计信息（需要登录）"""
    user = await require_auth(request)
    all_articles = article_store.get_all(per_page=1)
    sources = article_store.get_sources()
    tasks = task_manager.get_all()

    return JSONResponse({
        "total_articles": all_articles["total"],
        "total_sources": len(sources),
        "sources": sources,
        "total_tasks": len(tasks),
        "recent_tasks": tasks[-5:],
    })


# ========================================================================
# WebSocket
# ========================================================================


# ========================================================================
# 调试端点（临时）
# ========================================================================

@app.get("/api/debug/article/{article_id}")
async def api_debug_article(article_id: str, request: Request):
    """调试用：查看文章内容（绕过 PowerShell 编码问题）"""
    user = await require_auth(request)
    
    import sqlite3
    from pathlib import Path
    
    # 尝试多个可能的数据库路径
    possible_paths = [
        Path(__file__).parent.parent / "data" / "content_aggregator.db",
        Path(__file__).parent.parent / "data" / "content.db",
        Path("data/content_aggregator.db"),
        Path("data/content.db"),
    ]
    
    db_path = None
    for p in possible_paths:
        if p.exists() and p.stat().st_size > 0:
            db_path = p
            break
    
    if not db_path:
        return JSONResponse({"error": "数据库未找到或为空"}, status_code=404)
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 尝试多个可能的表名
        table_names = ["articles", "Articles", "article"]
        row = None
        actual_table = None
        
        for table_name in table_names:
            try:
                cursor.execute(
                    f"SELECT id, title, source, LENGTH(content) as content_len, substr(content, 1, 1000) as content_preview "
                    f"FROM {table_name} WHERE id = ?",
                    (article_id,)
                )
                row = cursor.fetchone()
                if row:
                    actual_table = table_name
                    break
            except Exception:
                continue
        
        if not row:
            return JSONResponse({"error": "Article not found"}, status_code=404)
        
        result = {
            "id": row["id"],
            "title": row["title"],
            "source": row["source"],
            "content_length": row["content_len"],
            "content_preview": row["content_preview"],
            "is_likely_transcript": row["content_len"] > 1000,  # 字幕通常 > 1000 字符
            "table_used": actual_table,
            "db_path": str(db_path),
        }
        return JSONResponse(result)
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if "conn" in locals():
            conn.close()


@app.get("/api/debug/recent")
async def api_debug_recent(request: Request, limit: int = 5):
    """调试用：查看最近采集的文章（绕过 PowerShell 编码问题）"""
    user = await require_auth(request)
    
    import sqlite3
    from pathlib import Path
    
    possible_paths = [
        Path(__file__).parent.parent / "data" / "content_aggregator.db",
        Path(__file__).parent.parent / "data" / "content.db",
    ]
    
    db_path = None
    for p in possible_paths:
        if p.exists() and p.stat().st_size > 0:
            db_path = p
            break
    
    if not db_path:
        return JSONResponse({"error": "数据库未找到或为空"}, status_code=404)
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        table_names = ["articles", "Articles", "article"]
        articles = []
        actual_table = None
        
        for table_name in table_names:
            try:
                cursor.execute(
                    f"SELECT id, title, source, LENGTH(content) as content_len "
                    f"FROM {table_name} ORDER BY ROWID DESC LIMIT ?",
                    (limit,)
                )
                articles = [dict(row) for row in cursor.fetchall()]
                if articles:
                    actual_table = table_name
                    break
            except Exception:
                continue
        
        if not articles:
            return JSONResponse({"error": "No articles found"}, status_code=404)
        
        return JSONResponse({
            "recent_articles": articles,
            "table_used": actual_table,
            "db_path": str(db_path),
        })
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        if "conn" in locals():
            conn.close()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """实时任务推送"""
    await ws.accept()
    ws_connections.append(ws)
    try:
        while True:
            # 接收心跳
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if ws in ws_connections:
            ws_connections.remove(ws)


# ========================================================================
# 定时调度器
# ========================================================================

async def _start_scheduler_bg():
    """后台启动调度器（不阻塞 uvicorn startup）"""
    global bg_scheduler
    jobs = CONFIG.get("scheduler", {}).get("jobs", [])
    bg_scheduler = BackgroundScheduler(CONFIG, article_store, task_manager, broadcast_ws)
    bg_scheduler.load_jobs(jobs)
    try:
        await bg_scheduler.start()
        logger.info(f"定时调度器已启动，共 {len(jobs)} 个任务")
    except Exception as e:
        logger.error(f"调度器启动失败: {e}")


@app.on_event("startup")
async def on_startup():
    """服务器启动时初始化后台调度器（非阻塞）"""
    # Fire-and-forget: 在后台任务中运行，不阻塞 uvicorn startup
    asyncio.create_task(_start_scheduler_bg())


@app.on_event("shutdown")
async def on_shutdown():
    """服务器关闭时停止调度器"""
    global bg_scheduler
    if bg_scheduler:
        await bg_scheduler.stop()


@app.get("/scheduler", response_class=HTMLResponse)
async def page_scheduler(request: Request):
    """定时任务管理页面"""
    jobs = bg_scheduler.list_jobs() if bg_scheduler else []
    sources = _get_available_sources()
    return render_template("scheduler.html", {
        "jobs": jobs,
        "sources": sources,
    })


@app.get("/api/schedules")
async def api_list_schedules(request: Request):
    """获取定时任务列表（需要登录）"""
    user = await require_auth(request)
    if not bg_scheduler:
        return JSONResponse({"jobs": []})
    return JSONResponse({"jobs": bg_scheduler.list_jobs()})


@app.post("/api/schedules")
async def api_create_schedule(request: Request):
    """创建定时任务（需要登录）"""
    user = await require_auth(request)
    global bg_scheduler
    data = await request.json()
    job = bg_scheduler.create_job(data) if bg_scheduler else None
    if job:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        if bg_scheduler and job["enabled"]:
            asyncio.create_task(bg_scheduler._job_loop(job))
        return JSONResponse({"job": job})
    return JSONResponse({"error": "创建失败"}, status_code=500)


@app.put("/api/schedules/{job_id}")
async def api_update_schedule(job_id: str, request: Request):
    """更新定时任务（需要登录）"""
    user = await require_auth(request)
    global bg_scheduler
    data = await request.json()
    job = bg_scheduler.update_job(job_id, data) if bg_scheduler else None
    if job:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        return JSONResponse({"job": job})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.delete("/api/schedules/{job_id}")
async def api_delete_schedule(job_id: str, request: Request):
    """删除定时任务（需要登录）"""
    user = await require_auth(request)
    global bg_scheduler
    ok = bg_scheduler.delete_job(job_id) if bg_scheduler else False
    if ok:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.post("/api/schedules/{job_id}/toggle")
async def api_toggle_schedule(job_id: str, request: Request):
    """启用/禁用定时任务（需要登录）"""
    user = await require_auth(request)
    global bg_scheduler
    job = bg_scheduler.toggle_job(job_id) if bg_scheduler else None
    if job:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        return JSONResponse({"job": job})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.post("/api/schedules/{job_id}/run")
async def api_run_schedule_now(job_id: str, request: Request):
    """立即执行定时任务（一次）（需要登录）"""
    user = await require_auth(request)
    global bg_scheduler
    job = await bg_scheduler.run_now(job_id) if bg_scheduler else None
    if job:
        return JSONResponse({"job": job, "message": f"任务「{job['name']}」已触发"})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.get("/api/schedules/{job_id}/history")
async def api_schedule_history(job_id: str, request: Request, limit: int = Query(default=20)):
    """查看定时任务历史（需要登录）"""
    user = await require_auth(request)
    if not bg_scheduler:
        return JSONResponse({"history": []})
    return JSONResponse({"history": bg_scheduler.get_history(job_id, limit)})


# ── 辅助函数 ───────────────────────────────────────────────────────────

def _get_available_sources() -> list[dict]:
    """从配置中提取所有可用数据源"""
    sources = []
    src_cfg = CONFIG.get("sources", {})
    for rss in src_cfg.get("rss", []):
        if isinstance(rss, dict) and rss.get("url"):
            sources.append({
                "type": "rss",
                "name": rss.get("name", rss["url"]),
                "url": rss["url"],
                "enabled": rss.get("enabled", True),
            })
    for url in src_cfg.get("sitemap", {}).get("sites", []):
        if isinstance(url, str):
            sources.append({"type": "sitemap", "name": url, "url": url, "enabled": True})
    yt = src_cfg.get("youtube", {})
    if yt.get("api_key"):
        sources.append({"type": "youtube", "name": "YouTube", "url": "", "enabled": True})
    return sources


def _save_schedules_to_config(jobs: list[dict]) -> None:
    """保存任务列表到 config.yaml"""
    global CONFIG
    CONFIG.setdefault("scheduler", {})
    CONFIG["scheduler"]["jobs"] = jobs
    save_config(CONFIG)


# ========================================================================
# 模型管理 API （多模型支持）
# ========================================================================

def _migrate_config_models(config: dict) -> dict:
    """将旧版 config 迁移到新版多模型结构"""
    llm = config.setdefault("llm", {})
    if "base_url" in llm and "models" not in llm:
        old_model_id = llm.get("model", "default")
        llm["models"] = [{
            "id": "default",
            "name": "默认模型",
            "base_url": llm.get("base_url", "http://127.0.0.1:19000/proxy/llm"),
            "api_key": llm.get("api_key", ""),
            "model_id": old_model_id,
            "is_default": True,
        }]
        llm["default_model_id"] = "default"
        llm.pop("base_url", None)
        llm.pop("model", None)
        llm.pop("api_key", None)
    elif "models" not in llm:
        llm["models"] = [{
            "id": "default", "name": "默认模型",
            "base_url": "http://127.0.0.1:19000/proxy/llm",
            "api_key": "", "model_id": "qclaw/pool-hy3-preview",
            "is_default": True,
        }]
        llm["default_model_id"] = "default"

    asr = config.setdefault("asr", {})
    if "api_endpoint" in asr and "models" not in asr:
        asr["models"] = [{
            "id": "default", "name": "默认ASR",
            "base_url": asr.get("api_endpoint", ""),
            "api_key": asr.get("api_key", ""),
            "model_id": "whisper-1", "is_default": True,
        }]
        asr["default_model_id"] = "default"
        asr.pop("api_endpoint", None)
        asr.pop("api_key", None)
    elif "models" not in asr:
        asr["models"] = []

    # 图片生成模型：内置预设（即梦 + Vidu）
    image = config.setdefault("image", {})
    if "models" not in image or not image["models"]:
        image["models"] = [
            {
                "id": "jimeng",
                "name": "即梦图片生成4.0",
                "base_url": "https://visual.volcengineapi.com",
                "api_key": "",
                "secret_key": "",
                "model_id": "jimeng_t2i_v40",
                "provider": "jimeng",
                "is_default": True,
            },
            {
                "id": "vidu",
                "name": "Vidu图片生成",
                "base_url": "https://api.vidu.cn",
                "api_key": "",
                "secret_key": "",
                "model_id": "viduq2",
                "provider": "vidu",
                "is_default": False,
            },
        ]
        image["default_model_id"] = "jimeng"

    return config


@app.get("/api/models/{model_type}")
async def api_get_models(request: Request, model_type: str):
    """获取模型列表（需要登录）"""
    user = await require_auth(request)
    if model_type not in ("llm", "asr", "image"):
        raise HTTPException(status_code=400, detail="不支持的模型类型")
    config = _migrate_config_models(load_config())
    models = config.get(model_type, {}).get("models", [])
    default_id = config.get(model_type, {}).get("default_model_id", "")
    # 为每个模型添加 key_preview（解密后的前4位明文）
    from settings_crypto import decrypt_value
    for m in models:
        raw = m.get("api_key", "")
        k = decrypt_value(raw)
        m["key_preview"] = k[:4] if len(k) >= 4 else k
        # Also for secret_key (Jimeng)
        sraw = m.get("secret_key", "")
        sk = decrypt_value(sraw)
        m["secret_key_preview"] = sk[:4] if len(sk) >= 4 else sk
    return {"models": models, "default_model_id": default_id}


@app.post("/api/models/{model_type}")
async def api_add_model(model_type: str, request: Request):
    """添加模型（需要登录）"""
    user = await require_auth(request)
    if model_type not in ("llm", "asr", "image"):
        raise HTTPException(status_code=400, detail="不支持的模型类型")
    # 图片模型是内置预设，不开放添加
    if model_type == "image":
        raise HTTPException(status_code=400, detail="图片生成模型为内置预设，不支持添加")
    data = await request.json()
    name = data.get("name", "").strip()
    base_url = data.get("base_url", "").strip()
    api_key = data.get("api_key", "").strip()
    model_id = data.get("model_id", "").strip()
    if not name or not base_url or not model_id:
        raise HTTPException(status_code=400, detail="名称、API 端点、模型 ID 不能为空")
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="API 端点必须以 http:// 或 https:// 开头")
    config = _migrate_config_models(load_config())
    models = config.setdefault(model_type, {}).setdefault("models", [])
    new_id = name.lower().replace(" ", "-").replace("_", "-")
    # 过滤非 ASCII 字符，确保 URL 安全
    import re
    clean_id = re.sub(r'[^a-z0-9-]', '', new_id)
    if not clean_id or len(clean_id) < 2:
        import uuid
        clean_id = "model-" + uuid.uuid4().hex[:8]
    new_id = clean_id
    existing_ids = {m["id"] for m in models}
    if new_id in existing_ids:
        suffix = 2
        while f"{new_id}-{suffix}" in existing_ids:
            suffix += 1
        new_id = f"{new_id}-{suffix}"
    new_model = {
        "id": new_id, "name": name,
        "base_url": base_url, "api_key": api_key,
        "model_id": model_id, "is_default": len(models) == 0,
    }
    models.append(new_model)
    if new_model["is_default"]:
        config[model_type]["default_model_id"] = new_id
    save_config(config)
    logger.info(f"[模型] 新增 {model_type}: {name} (id: {new_id})")
    return {"status": "success", "model": new_model}


@app.put("/api/models/{model_type}/{model_id}")
async def api_update_model(model_type: str, model_id: str, request: Request):
    """更新模型（需要登录）"""
    user = await require_auth(request)
    if model_type not in ("llm", "asr", "image"):
        raise HTTPException(status_code=400, detail="不支持的模型类型")
    data = await request.json()
    config = _migrate_config_models(load_config())
    models = config.setdefault(model_type, {}).setdefault("models", [])
    target = next((m for m in models if m["id"] == model_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"模型 '{model_id}' 不存在")
    if "name" in data:
        target["name"] = data["name"].strip()
    if model_type != "image":
        if "base_url" in data:
            url = data["base_url"].strip()
            if url and not url.startswith(("http://", "https://")):
                raise HTTPException(status_code=400, detail="API 端点必须以 http:// 或 https:// 开头")
            target["base_url"] = url
        if "model_id" in data:
            val = data["model_id"].strip()
            if not val:
                raise HTTPException(status_code=400, detail="模型 ID 不能为空")
            target["model_id"] = val
    if "api_key" in data:
        target["api_key"] = data["api_key"].strip()
    if model_type == "image" and "secret_key" in data:
        target["secret_key"] = data["secret_key"].strip()
    save_config(config)
    return {"status": "success", "model": target}


@app.delete("/api/models/{model_type}/{model_id}")
async def api_delete_model(model_type: str, model_id: str, request: Request):
    """删除模型（需要登录）"""
    user = await require_auth(request)
    if model_type not in ("llm", "asr", "image"):
        raise HTTPException(status_code=400, detail="不支持的模型类型")
    config = _migrate_config_models(load_config())
    models = config.setdefault(model_type, {}).setdefault("models", [])
    if model_type == "image":
        raise HTTPException(status_code=400, detail="内置预设模型不可删除")
    if len(models) <= 1:
        raise HTTPException(status_code=400, detail="至少需要保留一个模型")
    idx = next((i for i, m in enumerate(models) if m["id"] == model_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"模型 '{model_id}' 不存在")
    removed = models.pop(idx)
    if config[model_type].get("default_model_id") == model_id:
        models[0]["is_default"] = True
        config[model_type]["default_model_id"] = models[0]["id"]
    save_config(config)
    return {"status": "success", "message": f"已删除模型 '{removed['name']}'"}


@app.post("/api/models/{model_type}/{model_id}/default")
async def api_set_default_model(model_type: str, model_id: str, request: Request):
    """设置默认模型（需要登录）"""
    user = await require_auth(request)
    if model_type not in ("llm", "asr", "image"):
        raise HTTPException(status_code=400, detail="不支持的模型类型")
    config = _migrate_config_models(load_config())
    models = config.setdefault(model_type, {}).setdefault("models", [])
    found = any(m["id"] == model_id for m in models)
    if not found:
        raise HTTPException(status_code=404, detail=f"模型 '{model_id}' 不存在")
    for m in models:
        m["is_default"] = (m["id"] == model_id)
    config[model_type]["default_model_id"] = model_id
    save_config(config)
    return {"status": "success", "message": "默认模型已更新"}


# ========================================================================
# 认证页面路由
# ========================================================================

@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    """登录页面"""
    return render_template("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def page_register(request: Request):
    """注册页面"""
    return render_template("register.html", {"request": request})


@app.get("/auth/forgot", response_class=HTMLResponse)
async def page_forgot_password(request: Request):
    """忘记密码页面"""
    return render_template("forgot_password.html", {"request": request})


@app.get("/auth/reset", response_class=HTMLResponse)
async def page_reset_password(request: Request, token: str = ""):
    """重置密码页面（token 从 URL 参数获取）"""
    return render_template("reset_password.html", {"request": request, "token": token})