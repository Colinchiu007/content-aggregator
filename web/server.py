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
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Form, Query, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from loguru import logger

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from content_aggregator.workflows.pipeline import ContentPipeline
from content_aggregator.models import Article, Content


# ========================================================================
# 配置加载
# ========================================================================

def load_config(config_path: str | None = None) -> dict:
    """加载 YAML 配置文件"""
    import yaml

    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    if path.exists():
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def save_config(config: dict, config_path: str | None = None) -> bool:
    """保存配置到 YAML 文件"""
    import yaml

    path = Path(config_path) if config_path else Path(__file__).parent.parent.parent / "config" / "config.yaml"
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

    def add(self, article: dict):
        """添加文章"""
        article["collected_at"] = datetime.now().isoformat()
        self.articles.insert(0, article)  # 最新的在前面
        self.save()

    def add_batch(self, articles: list[dict]):
        """批量添加"""
        now = datetime.now().isoformat()
        for a in articles:
            a["collected_at"] = now
        self.articles = articles + self.articles
        self.save()

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

# 模板
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 存储
article_store = ArticleStore(CONFIG.get("export", {}).get("output_dir", "./output/exports").replace("/exports", "").replace("/output", "./data"))
task_manager = TaskManager()

# WebSocket 连接池
ws_connections: list[WebSocket] = []


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
    configured_sources = []
    source_labels = {
        "rss": "RSS 订阅",
        "youtube": "YouTube",
        "twitter": "X (Twitter)",
        "tiktok": "TikTok",
        "douyin": "抖音",
        "xiaohongshu": "小红书",
        "wechat": "微信公众号",
        "sitemap": "Sitemap",
        "api": "自定义 API",
    }
    for src_type, src_cfg in sources_config.items():
        count = 0
        if isinstance(src_cfg, list):
            count = sum(1 for s in src_cfg if s.get("enabled", True))
        elif isinstance(src_cfg, dict):
            for list_key in ["channels", "users", "accounts", "sites", "endpoints"]:
                items = src_cfg.get(list_key, [])
                if items:
                    count = sum(1 for s in items if s.get("enabled", True))
                    break
            if count == 0 and (src_cfg.get("api_url") or src_cfg.get("base_url")):
                count = 1

        configured_sources.append({
            "type": src_type,
            "label": source_labels.get(src_type, src_type),
            "count": count,
        })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "sources_stats": sources_stats,
        "recent_articles": recent["items"][:5],
        "total_articles": article_store.get_all()["total"],
        "configured_sources": configured_sources,
        "tasks": task_manager.get_all()[-5:],
    })


@app.get("/articles", response_class=HTMLResponse)
async def page_articles(request: Request, page: int = 1, source: str | None = None):
    """文章列表"""
    result = article_store.get_all(page=page, per_page=20, source=source)
    sources = article_store.get_sources()
    return templates.TemplateResponse("articles.html", {
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
    return templates.TemplateResponse("article_detail.html", {
        "request": request,
        "article": article,
    })


@app.get("/sources", response_class=HTMLResponse)
async def page_sources(request: Request):
    """数据源管理"""
    sources_config = CONFIG.get("sources", {})
    return templates.TemplateResponse("sources.html", {
        "request": request,
        "sources_config": sources_config,
    })


@app.get("/compose", response_class=HTMLResponse)
async def page_compose(request: Request):
    """手动输入 → 改写 → 导出"""
    return templates.TemplateResponse("compose.html", {
        "request": request,
    })


@app.get("/tasks", response_class=HTMLResponse)
async def page_tasks(request: Request):
    """任务列表"""
    tasks = task_manager.get_all()
    return templates.TemplateResponse("tasks.html", {
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
                )

                # 存入 ArticleStore
                articles_data = [a.to_dict() for a in result.get("articles", [])]
                article_store.add_batch(articles_data)

                summary = result.get("summary", {})
                msg = f"采集完成：{summary.get('success', 0)} 个源成功，{summary.get('total_articles', 0)} 篇文章"
                task_manager.update(task_id, status="done", progress=100, message=msg, result=summary)
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


@app.post("/api/collect/url")
async def api_collect_url(
    url: str = Form(...),
    rewrite: bool = Form(default=True),
    formats: str | None = Form(default="markdown"),
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
                article = await pipeline.process_url(url, rewrite=rewrite)

                if article:
                    article_store.add(article.to_dict())
                    for fmt in fmt_list:
                        try:
                            pipeline.exporter.export(article, fmt)
                        except Exception as e:
                            logger.warning(f"导出失败 ({fmt}): {e}")

                    task_manager.update(task_id, status="done", progress=100,
                                        message=f"采集成功: {article.title}", result=article.to_dict())
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "done", "message": f"✅ {article.title}"})
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
async def api_rewrite(article_id: str = Form(...)):
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
                config = RewriteConfig(strategy=RewriteStrategy.REWRITE)
                result = await processor.rewrite(content, config)

                if result.success:
                    article["title"] = result.title or article["title"]
                    article["original_title"] = article.get("title", "")
                    article["content"] = result.rewritten_content
                    article["word_count"] = len(result.rewritten_content)
                    article_store.save()

                    task_manager.update(task_id, status="done", progress=100, message="改写完成")
                    await broadcast_ws({"type": "task_update", "task_id": task_id,
                                        "status": "done", "message": "改写完成"})
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
):
    """手动输入内容 → 改写/导出"""
    task_id = task_manager.create("compose", f"处理: {title[:30] if title else '手动输入'}")

    async def run_task():
        try:
            task_manager.update(task_id, status="running", message="正在处理...")

            from content_aggregator.processors.rewrite import RewriteProcessor, RewriteConfig, RewriteStrategy
            from content_aggregator.exporters import Exporter

            rewritten_content = content
            if action == "rewrite":
                async with RewriteProcessor(CONFIG) as processor:
                    c = Content(
                        id=str(__import__("uuid").uuid4()),
                        source_id="manual",
                        source_type="manual",
                        title=title,
                        content=content,
                    )
                    result = await processor.rewrite(c, RewriteConfig(strategy=RewriteStrategy.REWRITE))
                    if result.success:
                        rewritten_content = result.rewritten_content
                        title = result.title or title
                    else:
                        task_manager.update(task_id, status="error", message=f"改写失败: {result.error}")
                        return

            # 导出
            article = Article(
                id=str(__import__("uuid").uuid4()),
                title=title or "手动输入",
                content=rewritten_content,
                word_count=len(rewritten_content),
            )
            article_store.add(article.to_dict())

            output_dir = CONFIG.get("export", {}).get("output_dir", "./output/exports")
            exporter = Exporter(output_dir)
            path = exporter.export(article, format_type)

            task_manager.update(task_id, status="done", progress=100,
                                message=f"导出完成: {path}", result={"path": path})
            await broadcast_ws({"type": "task_update", "task_id": task_id,
                                "status": "done", "message": f"✅ 已导出到 {path}"})

        except Exception as e:
            task_manager.update(task_id, status="error", message=f"处理失败: {e}")

    asyncio.create_task(run_task())
    return JSONResponse({"task_id": task_id, "status": "started"})


@app.delete("/api/articles/{article_id}")
async def api_delete_article(article_id: str):
    """删除文章"""
    if article_store.delete(article_id):
        return JSONResponse({"success": True})
    return JSONResponse({"success": False, "error": "文章不存在"})


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