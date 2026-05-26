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

from fastapi import FastAPI, Request, Form, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from loguru import logger

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.models import Article, Content
from web.server_scheduler import BackgroundScheduler


# ========================================================================
# 配置加载
# ========================================================================

def load_config(config_path: str | None = None) -> dict:
    """加载 YAML 配置文件"""
    import yaml

    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).parent.parent / "config" / "config.yaml"

    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def save_config(config: dict, config_path: str | None = None) -> bool:
    """保存配置到 YAML 文件"""
    import yaml

    path = Path(config_path) if config_path else Path(__file__).parent.parent / "config" / "config.yaml"
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
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

    def get_by_id(self, article_id: str) -> dict | None:
        """按 ID 获取"""
        for a in self.articles:
            if a.get("id") == article_id:
                return a
        return None

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

    def create(self, task_type: str, description: str = "") -> str:
        """创建任务，返回 task_id"""
        task_id = f"task_{int(time.time())}_{id(self) % 10000}"
        self.tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "description": description,
            "status": "pending",  # pending / running / done / error
            "progress": 0,
            "message": "",
            "result": None,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "finished_at": None,
        }
        return task_id

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
        if status in ("done", "error"):
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

# 模板（绕过 Starlette Jinja2Templates，直接使用 Jinja2，修复 unhashable type: 'dict' 错误）
jinja_env = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    auto_reload=True,
)

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
    return HTMLResponse(content=html)

# 存储
article_store = ArticleStore(data_dir=str(BASE_DIR.parent / "data"))
task_manager = TaskManager()

# WebSocket 连接池
ws_connections: list[WebSocket] = []
bg_scheduler: BackgroundScheduler | None = None


async def broadcast_ws(message: dict):
    """广播消息到所有 WebSocket 客户端"""
    dead = []
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_connections.remove(ws)


# ========================================================================
# 页面路由
# ========================================================================

@app.get("/", response_class=HTMLResponse)
async def page_index(request: Request):
    """仪表盘"""
    sources_stats = article_store.get_sources()
    recent = article_store.get_all(page=1, per_page=10)

    # 数据源配置统计
    sources_config = CONFIG.get("sources", {})
    source_labels = {
        "rss": "RSS 订阅", "youtube": "YouTube", "twitter": "X (Twitter)",
        "tiktok": "TikTok", "douyin": "抖音", "xiaohongshu": "小红书",
        "wechat": "微信公众号", "sitemap": "Sitemap", "api": "自定义 API",
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

    return render_template("index.html", {
        "request": request,
        "sources_stats": sources_stats,
        "recent_articles": recent["items"][:5],
        "total_articles": article_store.get_all()["total"],
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


@app.get("/tasks", response_class=HTMLResponse)
async def page_tasks(request: Request):
    """任务列表"""
    tasks = task_manager.get_all()
    return render_template("tasks.html", {
        "request": request,
        "tasks": reversed(tasks),
    })


# ========================================================================
# API 路由
# ========================================================================

@app.post("/api/collect/all")
async def api_collect_all(
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发全源采集（后台任务）"""
    task_id = task_manager.create("collect_all", "全源采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="正在初始化流水线...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在初始化..."})

            async with ContentPipeline(CONFIG) as pipeline:
                result = await pipeline.process_all_sources(
                    rewrite=rewrite,
                    translate=bool(translate),
                    target_language=translate,
                    formats=fmt_list,
                    limit_per_source=limit,
                )

                # 存入 ArticleStore
                articles_objs = result.get("articles", [])
                logger.info(f"[DEBUG] 采集到文章数: {len(articles_objs)}")
                articles_data = [a.to_dict() for a in articles_objs]
                logger.info(f"[DEBUG] 转换为字典后文章数: {len(articles_data)}")
                added = article_store.add_batch(articles_data)
                logger.info(f"[DEBUG] 实际存储文章数: {added}, 存储后总数: {len(article_store.articles)}")
                # 提取 article_ids，供任务列表跳转使用
                article_ids = [a.id for a in articles_objs]

                summary = result.get("summary", {})
                msg = f"采集完成：{summary.get('success', 0)} 个源成功，{summary.get('total_articles', 0)} 篇文章"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary,
                    "article_ids": article_ids
                })
                await broadcast_ws({"type": "task_update", "task_id": task_id,
                                    "status": "done", "message": msg})

        except Exception as e:
            error_msg = f"采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})
            logger.error(error_msg, exc_info=True)

    asyncio.create_task(run_task())
    return JSONResponse({"task_id": task_id, "status": "started"})


# YouTube 采集

@app.post("/api/collect/youtube")
async def api_collect_youtube(
    rewrite: bool = Form(default=True),
    translate: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """触发 YouTube 采集（后台任务）"""
    task_id = task_manager.create("collect_youtube", "YouTube 采集")
    fmt_list = [f.strip() for f in formats.split(",") if f.strip()] if formats else ["markdown"]

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="正在采集 YouTube...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在采集 YouTube..."})

            async with ContentPipeline(CONFIG) as pipeline:
                # 只采集 YouTube 源
                result = await pipeline.process_source("youtube",
                    rewrite=rewrite,
                    translate=bool(translate),
                    target_language=translate,
                    formats=fmt_list,
                    limit_per_source=limit,
                )

                articles_objs = result.get("articles", [])
                articles_data = [a.to_dict() for a in articles_objs]
                added = article_store.add_batch(articles_data)
                article_ids = [a.id for a in articles_objs]

                summary = result.get("summary", {})
                msg = f"YouTube 采集完成：{summary.get('success', 0)} 个任务成功，{summary.get('total_articles', 0)} 篇"
                task_manager.update(task_id, status="done", progress=100, message=msg, result={
                    "summary": summary,
                    "article_ids": article_ids
                })
                await broadcast_ws({"type": "task_update", "task_id": task_id,
                                    "status": "done", "message": msg})

        except Exception as e:
            error_msg = f"YouTube 采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})
            logger.error(error_msg, exc_info=True)

    asyncio.create_task(run_task())
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/collect/url")
async def api_collect_url(
    url: str = Form(...),
    rewrite: bool = Form(default=True),
    strategy: str | None = Form(default=None),
    formats: str | None = Form(default="markdown"),
    limit: int | None = Form(default=None),
):
    """采集单个 URL"""
    task_id = task_manager.create("collect_url", f"采集: {url[:50]}")

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="正在采集...")
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "running", "message": "正在采集..."})

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
                                        "status": "done", "message": f"✅ 采集 {len(articles)} 篇"})
                else:
                    task_manager.update(task_id, status="error", message="采集失败：无内容")
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "error", "message": "采集失败"})

        except Exception as e:
            error_msg = f"采集失败: {e}"
            task_manager.update(task_id, status="error", message=error_msg)
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "error", "message": error_msg})

    asyncio.create_task(run_task())
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/rewrite")
async def api_rewrite(article_id: str = Form(...), strategy: str = Form(default="REWRITE"),
                         translate: str = Form(default="no")):
    """改写已有文章"""
    article = article_store.get_by_id(article_id)
    if not article:
        return JSONResponse({"success": False, "error": "文章不存在"})

    task_id = task_manager.create("rewrite", f"改写: {article.get('title', '')[:30]}")

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="正在改写...")

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
                config = RewriteConfig(
                    strategy=cfg_strategy,
                    translate_to="zh" if translate == "yes" else None,
                )
                result = await processor.rewrite(content, config)

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
                    article_store.save()

                    task_manager.update(task_id, status="done", progress=100,
                                        message="改写完成", result={"article_id": article_id})
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "done", "message": "改写完成", "article_id": article_id})
                else:
                    task_manager.update(task_id, status="error", message=f"改写失败: {result.error}")

        except Exception as e:
            task_manager.update(task_id, status="error", message=f"改写失败: {e}")

    asyncio.create_task(run_task())
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.post("/api/compose")
async def api_compose(
    title: str = Form(default=""),
    content: str = Form(...),
    action: str = Form(default="export"),
    format_type: str = Form(default="markdown"),
    strategy: str = Form(default="REWRITE"),
    translate: str = Form(default="no"),
):
    """手动输入内容 → 改写/导出"""
    task_id = task_manager.create("compose", f"处理: {title[:30] if title else '手动输入'}")

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="正在处理...")

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
                                "status": "done", "message": f"✅ 处理完成", "article_id": aid})

        except Exception as e:
            task_manager.update(task_id, status="error", message=f"处理失败: {e}")

    asyncio.create_task(run_task())
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.get("/api/articles/{article_id}")
async def api_get_article(article_id: str):
    """获取单篇文章"""
    article = article_store.get_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return JSONResponse(article)


@app.delete("/api/articles/{article_id}")
async def api_delete_article(article_id: str):
    """删除文章"""
    if article_store.delete(article_id):
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "文章不存在"})


@app.post("/api/export/pdf")
async def api_export_pdf(request: Request):
    """导出文章为 PDF"""
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
async def api_clear_articles():
    """清空文章"""
    article_store.clear()
    return JSONResponse({"success": True})


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str):
    """查询任务状态"""
    task = task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JSONResponse(task)


@app.get("/api/tasks")
async def api_list_tasks():
    """列出所有任务"""
    return JSONResponse(task_manager.get_all())


@app.get("/api/sources")
async def api_list_sources():
    """列出已配置的数据源"""
    sources = CONFIG.get("sources", {})
    result = {}
    for src_type, src_cfg in sources.items():
        if isinstance(src_cfg, list):
            result[src_type] = [{"name": s.get("name", ""), "enabled": s.get("enabled", True)} for s in src_cfg]
        elif isinstance(src_cfg, dict):
            entries = []
            for list_key in ["channels", "users", "accounts", "sites", "endpoints"]:
                for s in src_cfg.get(list_key, []):
                    entries.append({"name": s.get("name", ""), "enabled": s.get("enabled", True)})
            result[src_type] = entries
    return JSONResponse(result)


@app.post("/api/sources/rss")
async def api_add_rss_source(name: str = Form(...), url: str = Form(...), enabled: str = Form(default="on")):
    """添加 RSS 数据源"""
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
async def api_delete_rss_source(name: str):
    """删除 RSS 数据源"""
    global CONFIG
    rss_list = CONFIG.get("sources", {}).get("rss", [])
    original_len = len(rss_list)
    CONFIG["sources"]["rss"] = [s for s in rss_list if s.get("name") != name]
    if len(CONFIG["sources"]["rss"]) < original_len:
        if save_config(CONFIG):
            return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "未找到该源"})


@app.post("/api/sources/rss/{name}/toggle")
async def api_toggle_rss_source(name: str):
    """启用/禁用 RSS 数据源"""
    global CONFIG
    for s in CONFIG.get("sources", {}).get("rss", []):
        if s.get("name") == name:
            s["enabled"] = not s.get("enabled", True)
            if save_config(CONFIG):
                return JSONResponse({"success": True, "enabled": s["enabled"]})
    return JSONResponse({"success": False, "error": "未找到该源"})


@app.get("/api/config")
async def api_get_config():
    """获取配置（隐藏 API Key）"""
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
    """保存完整配置（含扩展数据源）——深度合并，null 值不覆盖已有配置"""
    global CONFIG
    try:
        body = await request.json()
        if "sources" in body:
            if "sources" not in CONFIG:
                CONFIG["sources"] = {}
            for key, value in body["sources"].items():
                if isinstance(value, dict) and isinstance(CONFIG["sources"].get(key), dict):
                    # 深度合并：只更新非 null、非空列表的字段（避免空 [] 覆盖已有配置）
                    for fk, fv in value.items():
                        if fv is not None and fv not in ([], ""):
                            CONFIG["sources"][key][fk] = fv
                elif value is not None:
                    CONFIG["sources"][key] = value
        if save_config(CONFIG):
            return JSONResponse({"success": True})
    except Exception as e:
        logger.error(f"Config save error: {e}")
    return JSONResponse({"success": False, "error": "保存失败"})


@app.get("/api/stats")
async def api_stats():
    """统计数据"""
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

@app.on_event("startup")
async def on_startup():
    """服务器启动时初始化后台调度器"""
    global bg_scheduler
    jobs = CONFIG.get("scheduler", {}).get("jobs", [])
    bg_scheduler = BackgroundScheduler(CONFIG, article_store, task_manager, broadcast_ws)
    bg_scheduler.load_jobs(jobs)
    await bg_scheduler.start()
    logger.info(f"定时调度器已启动，共 {len(jobs)} 个任务")


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
async def api_list_schedules():
    """列出所有定时任务"""
    if not bg_scheduler:
        return JSONResponse({"jobs": []})
    return JSONResponse({"jobs": bg_scheduler.list_jobs()})


@app.post("/api/schedules")
async def api_create_schedule(request: Request):
    """创建定时任务"""
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
    """更新定时任务"""
    global bg_scheduler
    data = await request.json()
    job = bg_scheduler.update_job(job_id, data) if bg_scheduler else None
    if job:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        return JSONResponse({"job": job})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.delete("/api/schedules/{job_id}")
async def api_delete_schedule(job_id: str):
    """删除定时任务"""
    global bg_scheduler
    ok = bg_scheduler.delete_job(job_id) if bg_scheduler else False
    if ok:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        return JSONResponse({"ok": True})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.post("/api/schedules/{job_id}/toggle")
async def api_toggle_schedule(job_id: str):
    """启用/禁用定时任务"""
    global bg_scheduler
    job = bg_scheduler.toggle_job(job_id) if bg_scheduler else None
    if job:
        _save_schedules_to_config(bg_scheduler.save_jobs())
        return JSONResponse({"job": job})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.post("/api/schedules/{job_id}/run")
async def api_run_schedule_now(job_id: str):
    """立即执行定时任务（一次）"""
    global bg_scheduler
    job = await bg_scheduler.run_now(job_id) if bg_scheduler else None
    if job:
        return JSONResponse({"job": job, "message": f"任务「{job['name']}」已触发"})
    return JSONResponse({"error": "任务不存在"}, status_code=404)


@app.get("/api/schedules/{job_id}/history")
async def api_schedule_history(job_id: str, limit: int = Query(default=20)):
    """获取任务执行历史"""
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