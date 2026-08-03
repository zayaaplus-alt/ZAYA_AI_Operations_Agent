from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

from .tasks import Task, get_task
from .tools import ToolExecutionManager, build_builtin_tools


@dataclass(slots=True)
class ScheduledTask:
    """Represents a scheduled task entry."""

    task_name: str
    run_once: bool = False
    interval_seconds: Optional[int] = None
    next_run_at: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    active: bool = True

    def should_run(self, current_time: Optional[datetime] = None) -> bool:
        current_time = current_time or datetime.now()
        return self.active and current_time >= self.next_run_at

    def mark_ran(self, current_time: Optional[datetime] = None) -> None:
        current_time = current_time or datetime.now()
        if self.run_once:
            self.active = False
        elif self.interval_seconds is not None:
            self.next_run_at = current_time + timedelta(seconds=self.interval_seconds)


class Scheduler:
    """Simple in-process scheduler for task execution."""

    def __init__(self) -> None:
        self._scheduled_tasks: list[ScheduledTask] = []
        self._lock = threading.RLock()
        self.tool_manager = ToolExecutionManager(registry=build_builtin_tools())

    def schedule_task(
        self,
        task_name: str,
        *,
        run_once: bool = False,
        interval_seconds: Optional[int] = None,
        start_at: Optional[datetime] = None,
    ) -> ScheduledTask:
        if not run_once and interval_seconds is None:
            raise ValueError("Recurring tasks require an interval")

        task = get_task(task_name)
        _ = task

        scheduled = ScheduledTask(
            task_name=task_name,
            run_once=run_once,
            interval_seconds=interval_seconds,
            next_run_at=start_at or datetime.now(),
        )
        with self._lock:
            self._scheduled_tasks.append(scheduled)
        return scheduled

    def list_scheduled(self) -> list[ScheduledTask]:
        with self._lock:
            return list(self._scheduled_tasks)

    def run_due_tasks(self, current_time: Optional[datetime] = None) -> list[Task]:
        current_time = current_time or datetime.now()
        completed: list[Task] = []
        with self._lock:
            for scheduled_task in list(self._scheduled_tasks):
                if not scheduled_task.should_run(current_time):
                    continue

                task = get_task(scheduled_task.task_name)
                task.run()
                completed.append(task)
                scheduled_task.mark_ran(current_time)

        return completed

    def run_forever(self, sleep_seconds: float = 1.0, stop_event: Optional[threading.Event] = None) -> None:
        stop_event = stop_event or threading.Event()
        while not stop_event.is_set():
            self.run_due_tasks()
            time.sleep(sleep_seconds)
