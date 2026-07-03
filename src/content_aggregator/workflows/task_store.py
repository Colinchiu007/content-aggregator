"""
任务存储与断点续跑

从 Y2A-Auto (github.com/fqscfqj/Y2A-Auto) task_manager.py 移植的断点续跑机制。

核心设计：
- SQLite 持久化任务状态和每个 item 的流水线阶段
- 进程崩溃后重启可自动恢复未完成的任务，从最后完成的阶段继续
- 支持任务取消（threading.Event 模式）、并发去重检查
- 内存感知：占用过高的回收策略

Schema:
    tasks: 记录每个调度任务/手动执行的状态
    items: 记录每个被处理的内容项的流水线阶段
    checkpoint_log: 流水线阶段变更日志（可选，用于调试）

Usage:
    store = TaskStore("data/tasks.db")
    
    # 创建任务
    task_id = await store.create_task("morning_rss", "rss", {"url": "..."})
    
    # 添加 item
    item_id = await store.add_item(task_id, content)
    
    # 更新 item 阶段
    await store.update_item_stage(item_id, "filtered")
    await store.update_item_stage(item_id, "rewritten", processed_data=json.dumps(article_dict))
    await store.update_item_stage(item_id, "completed")
    
    # 恢复: 找到需要继续处理的 items
    pending_items = await store.get_pending_items(task_id)
"""

import asyncio
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ============================================================
# 常量定义
# ============================================================

DEFAULT_DB_NAME = "tasks.db"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ItemStage(str, Enum):
    """流水线阶段（每个 item 的 checkpoint）"""
    COLLECTED = "collected"       # 已采集到原始数据
    FILTERED = "filtered"         # 已通过过滤器（敏感词+去重）
    REWRITING = "rewriting"       # 改写中（LLM 调用中）
    REWRITTEN = "rewritten"       # 已改写完成
    COMPLETED = "completed"       # 已转为 Article 且导出完成
    FAILED = "failed"             # 处理失败


# 恢复时认定为"需要回退重新处理"的阶段
RESUME_ROLLBACK_STAGES = {ItemStage.REWRITING}

# 恢复时认定为"已稳定完成，可跳过"的阶段
RESUME_SKIP_STAGES = {ItemStage.COMPLETED}

# 从哪些阶段开始重新处理
STAGE_PRIORITY = [
    ItemStage.COLLECTED,
    ItemStage.FILTERED,
    ItemStage.REWRITTEN,
]

# 所有有效流水线阶段
PROCESSING_STAGES = {s for s in ItemStage}


# ============================================================
# Schema & 模型
# ============================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    source_type     TEXT NOT NULL DEFAULT '',
    source_config   TEXT DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'pending',
    progress        INTEGER DEFAULT 0,
    total_items     INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    error           TEXT,
    scheduler_job   TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    started_at      TEXT,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    source_url      TEXT DEFAULT '',
    title           TEXT DEFAULT '',
    stage           TEXT NOT NULL DEFAULT 'collected',
    collected_data  TEXT,
    processed_data  TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE INDEX IF NOT EXISTS idx_items_task_id ON items(task_id);
CREATE INDEX IF NOT EXISTS idx_items_stage ON items(stage);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

CREATE TABLE IF NOT EXISTS checkpoint_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    item_id         TEXT,
    stage           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'started',
    message         TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cl_task_id ON checkpoint_log(task_id);
"""


# ============================================================
# 并发控制：Active Task 追踪 + 取消机制（从 Y2A 移植）
# ============================================================

_ACTIVE_TASK_IDS: set[str] = set()
_ACTIVE_TASKS_LOCK = threading.Lock()
_TASK_CANCEL_FLAGS: dict[str, threading.Event] = {}
_TASK_CANCEL_LOCK = threading.Lock()


def mark_task_active(task_id: str) -> bool:
    """标记任务为活跃中。False = 同 ID 任务已存在（防重复运行）"""
    if not task_id:
        return False
    with _ACTIVE_TASKS_LOCK:
        if task_id in _ACTIVE_TASK_IDS:
            return False
        _ACTIVE_TASK_IDS.add(task_id)
        return True


def mark_task_inactive(task_id: str) -> None:
    with _ACTIVE_TASKS_LOCK:
        _ACTIVE_TASK_IDS.discard(task_id)


def is_task_active(task_id: str) -> bool:
    if not task_id:
        return False
    with _ACTIVE_TASKS_LOCK:
        return task_id in _ACTIVE_TASK_IDS


def request_task_cancel(task_id: str) -> Optional[threading.Event]:
    """请求取消任务。返回 Event 用于等待确认"""
    if not task_id:
        return None
    with _TASK_CANCEL_LOCK:
        event = _TASK_CANCEL_FLAGS.get(task_id)
        if not event:
            event = threading.Event()
            _TASK_CANCEL_FLAGS[task_id] = event
        event.set()
    return event


def is_task_cancelled(task_id: str) -> bool:
    if not task_id:
        return False
    with _TASK_CANCEL_LOCK:
        event = _TASK_CANCEL_FLAGS.get(task_id)
        return bool(event and event.is_set())


def clear_task_cancel(task_id: str) -> None:
    if not task_id:
        return
    with _TASK_CANCEL_LOCK:
        _TASK_CANCEL_FLAGS.pop(task_id, None)


class TaskCancelledError(Exception):
    """任务已取消"""
    pass


# ============================================================
# 内存感知（从 Y2A Auto 移植）
# ============================================================

def _get_memory_usage_percent() -> float:
    """获取内存使用百分比"""
    try:
        import psutil
        memory = psutil.virtual_memory()
        return memory.percent
    except ImportError:
        return 50.0
    except Exception:
        return 50.0


def should_reduce_concurrency() -> bool:
    """内存超过 80% 时降低并发"""
    return _get_memory_usage_percent() > 80.0


# ============================================================
# 断点续跑异常
# ============================================================

class CheckpointRecoveryError(Exception):
    """断点恢复失败"""
    pass


# ============================================================
# TaskStore
# ============================================================

@dataclass
class TaskRecord:
    id: str
    name: str
    source_type: str = ""
    source_config: str = "{}"
    status: str = TaskStatus.PENDING.value
    progress: int = 0
    total_items: int = 0
    processed_items: int = 0
    error: Optional[str] = None
    scheduler_job: str = ""
    created_at: str = ""
    updated_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ItemRecord:
    id: str
    task_id: str
    source_url: str = ""
    title: str = ""
    stage: str = ItemStage.COLLECTED.value
    collected_data: Optional[str] = None
    processed_data: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    """
    SQLite 断点续跑存储。

    Thread-safe：使用连接池 + WAL 模式支持并发读写。
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._init_db()
        logger.info(f"[TaskStore] 初始化完成: {db_path}")

    def _init_db(self):
        """初始化数据库 Schema"""
        conn = self._get_conn()
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """获取新的数据库连接（每次调用创建）"""
        conn = sqlite3.connect(self.db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ============================================================
    # Task CRUD
    # ============================================================

    def create_task(
        self,
        name: str,
        source_type: str = "",
        source_config: dict | None = None,
        scheduler_job: str = "",
    ) -> str:
        """创建新任务，返回 task_id"""
        task_id = str(uuid.uuid4())
        now = _now()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO tasks (id, name, source_type, source_config, status, scheduler_job, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (task_id, name, source_type, json.dumps(source_config or {}),
                 TaskStatus.PENDING.value, scheduler_job, now, now)
            )
            conn.commit()
            logger.info(f"[TaskStore] 创建任务: {name} (id={task_id[:8]})")
            return task_id
        except Exception as e:
            logger.error(f"[TaskStore] 创建任务失败: {e}")
            raise
        finally:
            conn.close()

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        progress: int | None = None,
        total_items: int | None = None,
        processed_items: int | None = None,
        error: str | None = None,
    ) -> None:
        """更新任务状态"""
        now = _now()
        conn = self._get_conn()
        try:
            fields = ["status = ?", "updated_at = ?"]
            params: list[Any] = [status.value, now]

            if progress is not None:
                fields.append("progress = ?")
                params.append(progress)
            if total_items is not None:
                fields.append("total_items = ?")
                params.append(total_items)
            if processed_items is not None:
                fields.append("processed_items = ?")
                params.append(processed_items)
            if error is not None:
                fields.append("error = ?")
                params.append(error)

            if status in (TaskStatus.RUNNING,):
                fields.append("started_at = COALESCE(started_at, ?)")
                params.append(now)
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                fields.append("completed_at = ?")
                params.append(now)

            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
                params
            )
            conn.commit()
        finally:
            conn.close()

    def get_task(self, task_id: str) -> TaskRecord | None:
        """获取任务"""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return TaskRecord(**dict(row))
        finally:
            conn.close()

    def list_tasks(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskRecord]:
        """列出任务"""
        conn = self._get_conn()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                ).fetchall()
            return [TaskRecord(**dict(r)) for r in rows]
        finally:
            conn.close()

    def get_interrupted_tasks(self) -> list[TaskRecord]:
        """
        获取中断的任务（状态为 running/pending，但无活跃线程）。
        进程崩溃重启后调用此方法。
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT * FROM tasks
                   WHERE status IN ('running', 'pending')
                   ORDER BY updated_at DESC"""
            ).fetchall()
            tasks = []
            for r in rows:
                task = TaskRecord(**dict(r))
                if not is_task_active(task.id):
                    tasks.append(task)
            return tasks
        finally:
            conn.close()

    def delete_task(self, task_id: str) -> None:
        """删除任务及其 items"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM checkpoint_log WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM items WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # Item CRUD + Checkpoint
    # ============================================================

    def add_item(
        self,
        task_id: str,
        source_url: str = "",
        title: str = "",
        collected_data: str | None = None,
    ) -> str:
        """添加采集到的 item"""
        item_id = str(uuid.uuid4())
        now = _now()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO items (id, task_id, source_url, title, stage, collected_data, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (item_id, task_id, source_url, title or "",
                 ItemStage.COLLECTED.value, collected_data, now, now)
            )
            conn.commit()
            return item_id
        finally:
            conn.close()

    def update_item_stage(
        self,
        item_id: str,
        stage: ItemStage,
        processed_data: str | None = None,
        error: str | None = None,
    ) -> None:
        """更新 item 流水线阶段（checkpoint）"""
        now = _now()
        conn = self._get_conn()
        try:
            fields = ["stage = ?", "updated_at = ?"]
            params: list[Any] = [stage.value, now]
            if processed_data is not None:
                fields.append("processed_data = ?")
                params.append(processed_data)
            if error is not None:
                fields.append("error = ?")
                params.append(error)

            params.append(item_id)
            conn.execute(
                f"UPDATE items SET {', '.join(fields)} WHERE id = ?",
                params
            )
            conn.commit()
        finally:
            conn.close()

    def log_checkpoint(
        self,
        task_id: str,
        stage: str,
        item_id: str | None = None,
        status: str = "started",
        message: str | None = None,
    ) -> None:
        """写入流水线日志"""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT INTO checkpoint_log (task_id, item_id, stage, status, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, item_id, stage, status, message, _now())
            )
            conn.commit()
        finally:
            conn.close()

    def get_items_by_task(self, task_id: str) -> list[ItemRecord]:
        """获取任务的 items"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM items WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,)
            ).fetchall()
            return [ItemRecord(**dict(r)) for r in rows]
        finally:
            conn.close()

    def get_pending_items(
        self,
        task_id: str,
        # 恢复策略：以下阶段的 item 需要重新处理
        reprocess_stages: set[ItemStage] | None = None,
    ) -> list[ItemRecord]:
        """
        获取需要继续处理的 items（断点续跑核心）。

        恢复策略：
        - stage=completed → 跳过（已处理完成）
        - stage=rewriting → 回退到 rewritten 之前（LLM 调用不可恢复）
        - stage=failed → 重试
        - stage=collected/filtered/rewritten → 从该阶段继续

        Args:
            task_id: 任务 ID
            reprocess_stages: 需要跳过的阶段列表（默认跳过 completed）

        Returns:
            需要处理的 ItemRecord 列表（按 created_at 排序）
        """
        conn = self._get_conn()
        try:
            skip = reprocess_stages or RESUME_SKIP_STAGES
            skip_values = [s.value for s in skip]

            placeholders = ",".join("?" for _ in skip_values)
            rows = conn.execute(
                f"""SELECT * FROM items
                    WHERE task_id = ? AND stage NOT IN ({placeholders})
                    ORDER BY created_at ASC""",
                [task_id] + skip_values
            ).fetchall()
            return [ItemRecord(**dict(r)) for r in rows]
        finally:
            conn.close()

    def update_task_item_counts(self, task_id: str) -> None:
        """同步更新任务的 total_items / processed_items / progress"""
        conn = self._get_conn()
        try:
            counts = conn.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN stage = 'completed' THEN 1 ELSE 0 END) as done
                   FROM items WHERE task_id = ?""",
                (task_id,)
            ).fetchone()
            if counts:
                total = counts["total"] or 0
                done = counts["done"] or 0
                progress = int((done / max(total, 1)) * 100)
                conn.execute(
                    "UPDATE tasks SET total_items=?, processed_items=?, progress=?, updated_at=? WHERE id=?",
                    (total, done, progress, _now(), task_id)
                )
                conn.commit()
        finally:
            conn.close()

    # ============================================================
    # 恢复入口
    # ============================================================

    def detect_and_prepare_recovery(self, task_id: str) -> dict[str, Any]:
        """
        检测任务的恢复状态并返回恢复数据。

        Returns:
            {
                "task_id": str,
                "task_name": str,
                "recoverable": bool,          # 是否有可恢复的内容
                "total_items": int,
                "completed_items": int,
                "pending_items": int,          # 需要重新处理的 items 数
                "skip_items": [ItemRecord],    # 可跳过的 items（已完成）
                "reprocess_items": [ItemRecord],  # 需要重新处理的 items
            }
        """
        task = self.get_task(task_id)
        if not task:
            return {"recoverable": False, "error": "task not found"}

        all_items = self.get_items_by_task(task_id)
        skip_items: list[ItemRecord] = []
        reprocess_items: list[ItemRecord] = []

        for item in all_items:
            stage = ItemStage(item.stage)
            if stage in (ItemStage.COMPLETED,):
                skip_items.append(item)
            else:
                reprocess_items.append(item)

        return {
            "task_id": task_id,
            "task_name": task.name,
            "recoverable": len(reprocess_items) > 0,
            "total_items": len(all_items),
            "completed_items": len(skip_items),
            "pending_items": len(reprocess_items),
            "skip_items": skip_items,
            "reprocess_items": reprocess_items,
        }

    def get_active_tasks_summary(self) -> list[dict[str, Any]]:
        """获取所有活跃/中断任务的摘要"""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                """SELECT id, name, source_type, status, progress, total_items, processed_items, error, updated_at
                   FROM tasks WHERE status IN ('running', 'pending')
                   ORDER BY updated_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
