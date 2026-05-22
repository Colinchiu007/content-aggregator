"""
后台调度器模块 - 独立文件，避免与 scheduler.py 混淆
"""

import asyncio
import datetime
import re
import time
import uuid
from typing import Any

from loguru import logger

from content_aggregator.workflows.pipeline import ContentPipeline


class BackgroundScheduler:
    """
    轻量级后台调度器
    - 从 config.yaml 加载任务
    - 支持 interval / cron / once 三种类型
    - 每次执行调用 pipeline
    """

    def __init__(self, config: dict, article_store, task_manager, broadcast_fn):
        self.config = config
        self.article_store = article_store
        self.task_manager = task_manager
        self.broadcast = broadcast_fn
        self._tasks: list[dict] = []
        self._running = False
        self._handles: list[asyncio.Task] = []
        self._history: dict[str, list[dict]] = {}  # schedule_id -> execution records

    # ── 加载/保存 ────────────────────────────────────────────
    def load_jobs(self, jobs: list[dict]) -> None:
        """从配置列表加载任务"""
        self._tasks = []
        for job in jobs:
            job = dict(job)
            job.setdefault("id", str(uuid.uuid4()))
            job.setdefault("name", "未命名任务")
            job.setdefault("type", "interval")  # interval | cron | once
            job.setdefault("interval_hours", 1)
            job.setdefault("cron", "0 9 * * *")
            job.setdefault("sources", [])        # [] = all sources
            job.setdefault("keywords", [])       # [] = no filter
            job.setdefault("rewrite", True)
            job.setdefault("translate", "")
            job.setdefault("enabled", True)
            job.setdefault("last_run", None)
            job.setdefault("next_run", None)
            job.setdefault("status", "idle")      # idle | running | error
            job.setdefault("last_error", None)
            self._tasks.append(job)

        # 计算初始 next_run
        for t in self._tasks:
            if t["enabled"]:
                t["next_run"] = self._calc_next_run(t)

    def save_jobs(self) -> list[dict]:
        """返回可序列化的任务列表（不含运行时状态）"""
        result = []
        for t in self._tasks:
            result.append({
                "id": t["id"],
                "name": t["name"],
                "type": t["type"],
                "interval_hours": t["interval_hours"],
                "cron": t["cron"],
                "sources": t["sources"],
                "keywords": t["keywords"],
                "rewrite": t["rewrite"],
                "translate": t["translate"],
                "enabled": t["enabled"],
            })
        return result

    # ── CRUD ─────────────────────────────────────────────────
    def create_job(self, data: dict) -> dict:
        job = dict(data)
        job["id"] = job.get("id") or str(uuid.uuid4())
        job.setdefault("name", "未命名任务")
        job.setdefault("type", "interval")
        job.setdefault("interval_hours", 1)
        job.setdefault("cron", "0 9 * * *")
        job.setdefault("sources", [])
        job.setdefault("keywords", [])
        job.setdefault("rewrite", True)
        job.setdefault("translate", "")
        job.setdefault("enabled", True)
        job.setdefault("last_run", None)
        job.setdefault("next_run", None)
        job.setdefault("status", "idle")
        job.setdefault("last_error", None)
        self._tasks.append(job)
        if job["enabled"]:
            job["next_run"] = self._calc_next_run(job)
        return job

    def get_job(self, job_id: str) -> dict | None:
        for t in self._tasks:
            if t["id"] == job_id:
                return t
        return None

    def update_job(self, job_id: str, data: dict) -> dict | None:
        for i, t in enumerate(self._tasks):
            if t["id"] == job_id:
                # 只更新允许字段
                for key in ("name", "type", "interval_hours", "cron",
                            "sources", "keywords", "rewrite", "translate", "enabled"):
                    if key in data:
                        t[key] = data[key]
                if t["enabled"]:
                    t["next_run"] = self._calc_next_run(t)
                else:
                    t["next_run"] = None
                return t
        return None

    def delete_job(self, job_id: str) -> bool:
        for i, t in enumerate(self._tasks):
            if t["id"] == job_id:
                self._tasks.pop(i)
                return True
        return False

    def toggle_job(self, job_id: str) -> dict | None:
        for t in self._tasks:
            if t["id"] == job_id:
                t["enabled"] = not t["enabled"]
                if t["enabled"]:
                    t["next_run"] = self._calc_next_run(t)
                    t["status"] = "idle"
                else:
                    t["next_run"] = None
                return t
        return None

    # ── 启动 / 停止 ──────────────────────────────────────────
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for t in self._tasks:
            if t["enabled"]:
                handle = asyncio.create_task(self._job_loop(t))
                self._handles.append(handle)
        logger.info(f"BackgroundScheduler started, {len(self._handles)} jobs")

    async def stop(self) -> None:
        self._running = False
        for h in self._handles:
            h.cancel()
        await asyncio.gather(*self._handles, return_exceptions=True)
        self._handles.clear()
        logger.info("BackgroundScheduler stopped")

    async def _job_loop(self, job: dict) -> None:
        """单任务循环"""
        # interval 类型立即执行一次
        if job["type"] == "interval":
            await self._execute_job(job, is_first=True)
        elif job["type"] == "once":
            # once 等待到点执行一次
            await self._wait_until(job)
            if self._running:
                await self._execute_job(job)
            return

        while self._running:
            wait_sec = self._calc_wait(job)
            if wait_sec is None:
                break
            await asyncio.sleep(wait_sec)
            if self._running:
                await self._execute_job(job)

    async def _wait_until(self, job: dict) -> None:
        """等待 once 任务到点"""
        next_run = self._calc_next_run(job)
        if next_run:
            wait = (next_run - datetime.datetime.now()).total_seconds()
            if wait > 0:
                await asyncio.sleep(wait)

    async def run_now(self, job_id: str) -> dict | None:
        """手动立即执行任务"""
        job = self.get_job(job_id)
        if not job:
            return None
        asyncio.create_task(self._execute_job(job, is_manual=True))
        return job

    # ── 执行任务 ────────────────────────────────────────────
    async def _execute_job(self, job: dict, is_first: bool = False, is_manual: bool = False) -> None:
        job_id = job["id"]
        started_at = datetime.datetime.now()
        job["status"] = "running"

        record = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "job_name": job["name"],
            "started_at": started_at.isoformat(),
            "finished_at": None,
            "duration_sec": 0,
            "success": False,
            "error": None,
            "articles_count": 0,
            "is_manual": is_manual,
        }

        try:
            task_id = self.task_manager.create(
                f"scheduled:{job_id[:8]}",
                f"定时采集: {job['name']}"
            )

            # ── 构建关键词过滤列表 ──
            keywords = job.get("keywords", [])
            kw_lower = [k.lower().strip() for k in keywords if k.strip()] if keywords else []

            # ── 调用 pipeline ──
            collected_ids = []
            sources = job.get("sources", [])

            if sources:
                # 指定数据源采集
                for source in sources:
                    ids = await self._collect_source(source, job, kw_lower)
                    collected_ids.extend(ids)
            else:
                # 全源采集
                collected_ids = await self._collect_all(job, kw_lower)

            record["articles_count"] = len(collected_ids)
            record["success"] = True
            job["status"] = "idle"
            job["last_error"] = None

            duration = (datetime.datetime.now() - started_at).total_seconds()
            record["duration_sec"] = round(duration, 1)
            self.task_manager.update(task_id, status="done",
                message=f"完成，采集 {len(collected_ids)} 篇新文章", progress=100)

            msg = f"✅ 定时任务「{job['name']}」完成，采集 {len(collected_ids)} 篇新文章"
            logger.info(msg)
            await self.broadcast({"type": "toast", "message": msg, "level": "success"})

        except Exception as e:
            job["status"] = "error"
            job["last_error"] = str(e)
            duration = (datetime.datetime.now() - started_at).total_seconds()
            record["duration_sec"] = round(duration, 1)
            record["error"] = str(e)

            self.task_manager.update(task_id, status="error",
                message=f"执行失败: {e}")
            logger.error(f"定时任务「{job['name']}」失败: {e}")
            await self.broadcast({
                "type": "toast",
                "message": f"❌ 定时任务「{job['name']}」失败: {e}",
                "level": "error"
            })

        finally:
            job["last_run"] = datetime.datetime.now().isoformat()
            finished_at = datetime.datetime.now()
            record["finished_at"] = finished_at.isoformat()

            # 更新 next_run
            if job["enabled"]:
                job["next_run"] = self._calc_next_run(job)

            # 记录历史
            if job_id not in self._history:
                self._history[job_id] = []
            self._history[job_id].insert(0, record)
            # 只保留最近 50 条
            self._history[job_id] = self._history[job_id][:50]
            job["status"] = "idle"

    async def _collect_source(self, source: dict, job: dict, kw_lower: list[str]) -> list[str]:
        """采集单个数据源 —— 复用 ContentPipeline（与手动采集同路径）"""
        from content_aggregator.workflows.pipeline import ContentPipeline

        source_type = source.get("type", "rss")
        url = source.get("url", "")
        if not url:
            return []

        collected_ids = []

        if source_type == "rss":
            # 复用 ContentPipeline.process_url（与 /api/collect/url 相同路径）
            try:
                logger.info(f"[Scheduler] 开始采集 RSS: {url}")
                async with ContentPipeline(self.config) as pipeline:
                    articles = await pipeline.process_url(
                        url=url,
                        rewrite=False,
                        limit=None,
                    )
                    logger.info(f"[Scheduler] process_url 返回 {len(articles)} 篇")

                    # ⚠️ 必须在 async with 块内处理文章！
                    # 退出块时 __aexit__() 会清理内部状态
                    for article in articles:
                        # 关键词过滤
                        if kw_lower:
                            title = (article.title or "").lower()
                            content_text = (article.content or "").lower()
                            if not any(k in title or k in content_text for k in kw_lower):
                                continue

                        # 存储
                        d = article.to_dict() if hasattr(article, "to_dict") else {
                            "title": article.title or "",
                            "content": article.content or "",
                            "source": article.source or source_type,
                            "source_url": article.url or "",
                            "author": article.author or "",
                            "published_at": article.published_at,
                        }
                        article_id = self.article_store.add(d)
                        if article_id:
                            collected_ids.append(str(article_id))
                        elif article_id is not None:
                            # 可能是重复文章，记录一下
                            logger.debug(f"[Scheduler] 文章可能重复: {article.title!r:.40s}")

                    logger.info(f"[Scheduler] RSS {url} → 采集 {len(collected_ids)} 篇")

            except Exception as e:
                logger.warning(f"[Scheduler] RSS {url} 失败: {e}")
                import traceback; logger.warning(traceback.format_exc())
                return collected_ids

            return collected_ids

        else:
            # 非 RSS 源：回退到直接用采集器（后续改为 ContentPipeline）
            logger.warning(f"[Scheduler] 非 RSS 源暂未适配: {source_type}")
            return []
    async def _collect_all(self, job: dict, kw_lower: list[str]) -> list[str]:
        """全源采集（复用 ContentPipeline，与手动采集同路径）"""
        async with ContentPipeline(self.config) as pipeline:
            result = await pipeline.process_all_sources(
                rewrite=job.get("rewrite", False),
                translate=bool(job.get("translate")),
                target_language=job.get("translate"),
                seo=False,
                formats=None,
                limit_per_source=None,
            )

        articles = result.get("articles", [])
        collected_ids = []
        for article in articles:
            # 关键词过滤
            if kw_lower:
                title = (article.title or "").lower()
                content = (article.content or "").lower()
                if not any(k in title or k in content for k in kw_lower):
                    continue
            article_id = self.article_store.add(article.to_dict())
            if article_id:
                collected_ids.append(str(article_id))
        return collected_ids

    # ── 调度时间计算 ───────────────────────────────────────
    def _calc_next_run(self, job: dict) -> str | None:
        """返回下次执行 ISO 时间字符串，无有效计划返回 None"""
        jtype = job.get("type", "interval")

        if jtype == "once":
            run_at = job.get("run_at") or job.get("cron")
            if not run_at:
                return None
            try:
                dt = datetime.datetime.fromisoformat(run_at)
                return dt.isoformat()
            except Exception:
                return None

        if jtype == "cron":
            cron_str = job.get("cron", "0 9 * * *")
            dt = self._parse_cron_next(cron_str)
            return dt.isoformat() if dt else None

        # interval
        interval_h = job.get("interval_hours", 1)
        next_dt = datetime.datetime.now() + datetime.timedelta(hours=interval_h)
        return next_dt.isoformat()

    def _calc_wait(self, job: dict) -> float | None:
        """距下次执行的秒数"""
        next_run = self._calc_next_run(job)
        if not next_run:
            return None
        try:
            next_dt = datetime.datetime.fromisoformat(next_run)
            wait = (next_dt - datetime.datetime.now()).total_seconds()
            return max(0, wait)
        except Exception:
            return None

    def _parse_cron_next(self, cron_expr: str) -> datetime.datetime | None:
        """计算 cron 表达式下一次匹配的时间"""
        try:
            parts = cron_expr.strip().split()
            if len(parts) < 5:
                return None
            minute_p, hour_p, day_p, month_p, weekday_p = parts[:5]

            now = datetime.datetime.now()
            candidate = now + datetime.timedelta(minutes=1)

            for _ in range(366 * 24 * 60):
                if (self._match_field(candidate.minute, minute_p) and
                        self._match_field(candidate.hour, hour_p) and
                        self._match_field(candidate.day, day_p) and
                        self._match_field(candidate.month, month_p) and
                        self._match_cron_weekday(candidate, weekday_p)):
                    return candidate
                candidate += datetime.timedelta(minutes=1)
            return None
        except Exception:
            return None

    def _match_field(self, value: int, pattern: str) -> bool:
        if pattern == "*":
            return True
        if pattern.startswith("*/"):
            return value % int(pattern[2:]) == 0
        if "," in pattern:
            return value in [int(x) for x in pattern.split(",")]
        if "-" in pattern and "/" not in pattern:
            start, end = pattern.split("-")
            return int(start) <= value <= int(end)
        try:
            return value == int(pattern)
        except ValueError:
            return False

    def _match_cron_weekday(self, dt: datetime.datetime, pattern: str) -> bool:
        """Python weekday: 0=周一, Cron: 0=周日"""
        if pattern == "*":
            return True
        # 转换为 Cron 周：0=周日
        cron_wd = 6 if dt.weekday() == 6 else dt.weekday() + 1
        return self._match_field(cron_wd, pattern)

    # ── 历史记录 ────────────────────────────────────────────
    def get_history(self, job_id: str, limit: int = 20) -> list[dict]:
        return self._history.get(job_id, [])[:limit]

    def list_jobs(self) -> list[dict]:
        return [
            {
                "id": t["id"],
                "name": t["name"],
                "type": t["type"],
                "interval_hours": t["interval_hours"],
                "cron": t["cron"],
                "sources": t["sources"],
                "keywords": t["keywords"],
                "rewrite": t["rewrite"],
                "translate": t["translate"],
                "enabled": t["enabled"],
                "last_run": t.get("last_run"),
                "next_run": t.get("next_run"),
                "status": t.get("status", "idle"),
                "last_error": t.get("last_error"),
            }
            for t in self._tasks
        ]
