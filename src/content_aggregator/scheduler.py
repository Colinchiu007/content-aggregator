"""
定时任务调度器

支持 Cron 表达式配置定时任务，自动执行内容采集→改写→导出的完整流程。
支持一次性任务和循环任务。
"""

import asyncio
import datetime
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from loguru import logger


class ScheduleType(Enum):
    """调度类型"""
    ONCE = "once"           # 一次性任务
    INTERVAL = "interval"   # 间隔循环
    CRON = "cron"           # Cron 表达式


@dataclass
class ScheduleConfig:
    """调度配置"""
    name: str = "unnamed_task"
    # 调度类型
    schedule_type: ScheduleType = ScheduleType.INTERVAL
    # 间隔秒数（INTERVAL 类型）
    interval_seconds: int = 3600
    # Cron 表达式（CRON 类型），格式：分 时 日 月 周
    # 例如："0 9 * * *" 表示每天 9:00
    #      "*/15 * * * *" 表示每 15 分钟
    #      "0 9,18 * * 1-5" 表示工作日 9:00 和 18:00
    cron_expression: str = "0 9 * * *"
    # 一次性任务的执行时间
    run_at: datetime.datetime | None = None
    # 任务是否启用
    enabled: bool = True
    # 最大重试次数
    max_retries: int = 3
    # 重试间隔（秒）
    retry_interval: int = 60


@dataclass
class SchedulerResult:
    """调度结果"""
    task_name: str
    success: bool
    started_at: datetime.datetime
    finished_at: datetime.datetime | None = None
    duration_seconds: float = 0.0
    error: str | None = None
    execution_count: int = 0


class ContentScheduler:
    """
    定时任务调度器

    使用示例：
        scheduler = ContentScheduler(config)

        # 添加 RSS 定时采集任务
        scheduler.add_interval_task(
            name="ruanyifeng_daily",
            interval_seconds=3600,
            callback=my_rss_task
        )

        # 添加 Cron 任务
        scheduler.add_cron_task(
            name="morning_news",
            cron_expression="0 8 * * *",
            callback=morning_task
        )

        # 启动调度器
        await scheduler.start()
    """

    def __init__(self, config: dict[str, Any]):
        """
        初始化调度器

        参数：
            config: 配置字典，包含数据库、数据源等配置
        """
        self.config = config
        self._tasks: list[dict[str, Any]] = []
        self._running = False
        self._task_handles: list[asyncio.Task] = []
        self._execution_history: list[dict] = []

    def add_interval_task(
        self,
        name: str,
        interval_seconds: int,
        callback: Callable[[], Awaitable[Any]],
        enabled: bool = True,
        max_retries: int = 3
    ) -> None:
        """
        添加间隔循环任务

        参数：
            name: 任务名称
            interval_seconds: 间隔秒数
            callback: 异步回调函数
            enabled: 是否启用
            max_retries: 最大重试次数
        """
        task_config = {
            "name": name,
            "schedule_type": ScheduleType.INTERVAL,
            "interval_seconds": interval_seconds,
            "callback": callback,
            "enabled": enabled,
            "max_retries": max_retries,
            "retry_interval": 60,
            "execution_count": 0,
        }
        self._tasks.append(task_config)
        logger.info(f"Added interval task '{name}' every {interval_seconds}s")

    def add_cron_task(
        self,
        name: str,
        cron_expression: str,
        callback: Callable[[], Awaitable[Any]],
        enabled: bool = True,
        max_retries: int = 3
    ) -> None:
        """
        添加 Cron 定时任务

        参数：
            name: 任务名称
            cron_expression: Cron 表达式（分 时 日 月 周）
            callback: 异步回调函数
            enabled: 是否启用
            max_retries: 最大重试次数

        支持格式：
            "0 9 * * *"         - 每天 9:00
            "*/15 * * * *"      - 每 15 分钟
            "0 9,18 * * 1-5"    - 工作日 9:00 和 18:00
            "30 14 * * 0,6"     - 周末 14:30
        """
        task_config = {
            "name": name,
            "schedule_type": ScheduleType.CRON,
            "cron_expression": cron_expression,
            "callback": callback,
            "enabled": enabled,
            "max_retries": max_retries,
            "retry_interval": 60,
            "execution_count": 0,
            "next_run_time": None,
        }
        self._tasks.append(task_config)
        logger.info(f"Added cron task '{name}' with schedule '{cron_expression}'")

    def add_once_task(
        self,
        name: str,
        run_at: datetime.datetime,
        callback: Callable[[], Awaitable[Any]],
        enabled: bool = True
    ) -> None:
        """
        添加一次性任务

        参数：
            name: 任务名称
            run_at: 执行时间
            callback: 异步回调函数
            enabled: 是否启用
        """
        task_config = {
            "name": name,
            "schedule_type": ScheduleType.ONCE,
            "run_at": run_at,
            "callback": callback,
            "enabled": enabled,
            "execution_count": 0,
        }
        self._tasks.append(task_config)
        logger.info(f"Added once task '{name}' scheduled for {run_at}")

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        logger.info(f"Scheduler started with {len(self._tasks)} tasks")

        # 为每个任务启动协程
        for task in self._tasks:
            if task["enabled"]:
                handle = asyncio.create_task(self._run_task_loop(task))
                self._task_handles.append(handle)

        # 保持调度器运行
        try:
            await asyncio.Event().wait()  # 永远等待
        except asyncio.CancelledError:
            logger.info("Scheduler cancelled")
        finally:
            self._running = False

    async def stop(self) -> None:
        """停止调度器"""
        logger.info("Stopping scheduler...")
        self._running = False

        # 取消所有任务
        for handle in self._task_handles:
            handle.cancel()

        # 等待所有任务结束
        await asyncio.gather(*self._task_handles, return_exceptions=True)
        self._task_handles.clear()
        logger.info("Scheduler stopped")

    async def _run_task_loop(self, task: dict[str, Any]) -> None:
        """运行单个任务循环"""
        name = task["name"]
        schedule_type = task["schedule_type"]

        # 立即执行一次（适用于 INTERVAL）
        if schedule_type == ScheduleType.INTERVAL:
            await self._execute_task(task, first_run=True)

        while self._running:
            try:
                if schedule_type == ScheduleType.INTERVAL:
                    await asyncio.sleep(task["interval_seconds"])
                    await self._execute_task(task)

                elif schedule_type == ScheduleType.CRON:
                    next_time = self._get_next_cron_time(task["cron_expression"])
                    if next_time is None:
                        logger.error(f"Invalid cron expression for task '{name}': {task['cron_expression']}")
                        break

                    task["next_run_time"] = next_time
                    sleep_seconds = (next_time - datetime.datetime.now()).total_seconds()

                    if sleep_seconds > 0:
                        await asyncio.sleep(sleep_seconds)
                    await self._execute_task(task)

                elif schedule_type == ScheduleType.ONCE:
                    run_at = task["run_at"]
                    sleep_seconds = (run_at - datetime.datetime.now()).total_seconds()
                    if sleep_seconds > 0:
                        await asyncio.sleep(sleep_seconds)
                    await self._execute_task(task)
                    # 一次性任务执行完后退出循环
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task '{name}' loop error: {e}")
                await asyncio.sleep(5)

    async def _execute_task(self, task: dict[str, Any], first_run: bool = False) -> None:
        """执行单个任务"""
        name = task["name"]
        callback = task["callback"]
        max_retries = task.get("max_retries", 3)
        retry_interval = task.get("retry_interval", 60)

        started_at = datetime.datetime.now()
        last_error = None

        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()  # 同步函数

                finished_at = datetime.datetime.now()
                duration = (finished_at - started_at).total_seconds()

                logger.info(f"Task '{name}' executed successfully in {duration:.2f}s")
                task["execution_count"] += 1

                self._record_execution(
                    name=name,
                    success=True,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration=duration
                )
                return

            except Exception as e:
                last_error = e
                logger.warning(f"Task '{name}' attempt {attempt + 1}/{max_retries} failed: {e}")

                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_interval)

        finished_at = datetime.datetime.now()
        duration = (finished_at - started_at).total_seconds()
        error_msg = str(last_error) if last_error else "Unknown error"

        logger.error(f"Task '{name}' failed after {max_retries} attempts: {error_msg}")
        self._record_execution(
            name=name,
            success=False,
            started_at=started_at,
            finished_at=finished_at,
            duration=duration,
            error=error_msg
        )

    def _get_next_cron_time(self, cron_expr: str) -> datetime.datetime | None:
        """
        计算下一个符合 Cron 表达式的时间

        支持格式：分 时 日 月 周
        - * 表示任意值
        - */n 表示每隔 n
        - n,m 表示多值
        - n-m 表示范围
        """
        try:
            parts = cron_expr.strip().split()
            if len(parts) < 5:
                logger.error(f"Cron expression must have 5 fields: {cron_expr}")
                return None

            minute, hour, day, month, weekday = parts

            now = datetime.datetime.now()

            # 简单的下一次时间计算
            # 从当前时间+1分钟开始，找到下一个匹配的时间
            candidate = now + datetime.timedelta(minutes=1)

            for _ in range(366 * 24 * 60):  # 最多搜索 1 年
                if self._matches_cron(candidate, minute, hour, day, month, weekday):
                    return candidate
                candidate += datetime.timedelta(minutes=1)

            return None

        except Exception as e:
            logger.error(f"Error parsing cron expression '{cron_expr}': {e}")
            return None

    def _matches_cron(
        self,
        dt: datetime.datetime,
        minute: str,
        hour: str,
        day: str,
        month: str,
        weekday: str
    ) -> bool:
        """检查时间是否匹配 Cron 字段"""
        try:
            # 分钟
            if not self._match_cron_field(dt.minute, minute):
                return False

            # 小时
            if not self._match_cron_field(dt.hour, hour):
                return False

            # 日（day of month）
            if day != "*" and not self._match_cron_field(dt.day, day):
                return False

            # 月
            if month != "*" and not self._match_cron_field(dt.month, month):
                return False

            # 周（day of week，0=周日）
            if weekday != "*":
                # 转换：Python 的 weekday() 0=周一，Cron 通常 0=周日
                cron_weekday = dt.weekday()
                # 如果 dt.weekday() 是周一(0)，Cron 是 0，周日(6) vs Cron 6
                # 保持一致：Python weekday 0=周一，转换后 0=周日
                py_weekday = dt.weekday()
                # 转换为 Cron 格式（周日=0，周六=6）
                cron_wd = 6 if py_weekday == 6 else py_weekday + 1
                if not self._match_cron_field(cron_wd, weekday):
                    return False

            return True

        except Exception:
            return False

    def _match_cron_field(self, value: int, pattern: str) -> bool:
        """
        匹配单个 Cron 字段

        支持格式：
        - * : 任意值
        - */n : 每隔 n
        - n : 具体值
        - n,m,o : 多个值
        - n-m : 范围
        - n-m/d : 范围内每隔 d
        """
        if pattern == "*":
            return True

        # */n 格式
        if pattern.startswith("*/"):
            step = int(pattern[2:])
            return value % step == 0

        # n-m 范围
        range_match = re.match(r"^(\d+)-(\d+)(?:/(\d+))?$", pattern)
        if range_match:
            start, end, step = range_match.groups()
            step = int(step) if step else 1
            return any(i >= int(start) and i <= int(end) and (i - int(start)) % step == 0 for i in [value])

        # 逗号分隔多值
        if "," in pattern:
            return value in [int(x) for x in pattern.split(",")]

        # 单值
        return value == int(pattern)

    def _record_execution(
        self,
        name: str,
        success: bool,
        started_at: datetime.datetime,
        finished_at: datetime.datetime,
        duration: float,
        error: str | None = None
    ) -> None:
        """记录任务执行历史"""
        record = {
            "task_name": name,
            "success": success,
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": duration,
            "error": error,
        }
        self._execution_history.append(record)

        # 只保留最近 100 条记录
        if len(self._execution_history) > 100:
            self._execution_history = self._execution_history[-100:]

    def get_task_status(self) -> list[dict[str, Any]]:
        """获取所有任务状态"""
        return [
            {
                "name": task["name"],
                "schedule_type": task["schedule_type"].value,
                "enabled": task["enabled"],
                "execution_count": task.get("execution_count", 0),
                "next_run_time": task.get("next_run_time", None),
            }
            for task in self._tasks
        ]

    def get_execution_history(
        self,
        task_name: str | None = None,
        limit: int = 20
    ) -> list[dict[str, Any]]:
        """获取任务执行历史"""
        history = self._execution_history

        if task_name:
            history = [r for r in history if r["task_name"] == task_name]

        return history[-limit:]

    @property
    def running(self) -> bool:
        return self._running

    @property
    def task_count(self) -> int:
        return len(self._tasks)

    @property
    def enabled_task_count(self) -> int:
        return sum(1 for t in self._tasks if t["enabled"])