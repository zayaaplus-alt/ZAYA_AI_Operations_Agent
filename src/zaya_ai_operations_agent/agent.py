from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .memory import MemoryStore
from .scheduler import Scheduler
from .tasks import Task, get_task


@dataclass(slots=True)
class ExecutionRecord:
    """Represents a single agent execution."""

    task_name: str
    executed_at: str
    status: str
    details: str = ""


class Agent:
    """A simple agent framework for planning and executing tasks."""

    def __init__(self, memory_store: Optional[MemoryStore] = None, scheduler: Optional[Scheduler] = None) -> None:
        self.memory_store = memory_store
        self.scheduler = scheduler or Scheduler()
        self._history: list[ExecutionRecord] = []

    def _get_memory(self) -> MemoryStore:
        if self.memory_store is None:
            self.memory_store = MemoryStore(Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
        return self.memory_store

    def plan(self, task_name: str) -> list[str]:
        return [task_name]

    def execute(self, task_name: str) -> ExecutionRecord:
        task: Task = get_task(task_name)
        task.run()
        record = ExecutionRecord(
            task_name=task_name,
            executed_at=datetime.now().isoformat(),
            status="completed",
            details=f"Executed task '{task_name}'",
        )
        self._history.append(record)
        memory = self._get_memory()
        history_data = memory.get("agent_history", [])
        history_data.append(asdict(record))
        memory.set("agent_history", history_data)
        return record

    def history(self) -> list[ExecutionRecord]:
        memory = self._get_memory()
        stored_history = memory.get("agent_history", [])
        if stored_history and not self._history:
            self._history = [ExecutionRecord(**entry) for entry in stored_history]
        return list(self._history)

    def export_history(self, output_path: Path) -> Path:
        history_data = [asdict(record) for record in self.history()]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(history_data, indent=2), encoding="utf-8")
        return output_path

    def run_scheduled(self) -> list[ExecutionRecord]:
        self.scheduler.run_due_tasks()
        return self.history()
