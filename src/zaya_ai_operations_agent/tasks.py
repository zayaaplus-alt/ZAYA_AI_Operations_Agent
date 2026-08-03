from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(slots=True)
class Task:
    """Simple task definition for the operations agent."""

    name: str
    description: str = ""
    handler: Optional[Callable[[], None]] = None

    def run(self) -> None:
        if self.handler is None:
            raise ValueError(f"Task '{self.name}' has no handler")
        self.handler()


TASK_REGISTRY: dict[str, Task] = {}


def create_hello_task() -> Task:
    def handler() -> None:
        print("Hello from the AI Operations Agent")

    return Task(name="hello", description="Print a friendly greeting", handler=handler)


def initialize_tasks() -> dict[str, Task]:
    """Populate the task registry with built-in tasks."""

    TASK_REGISTRY.clear()
    TASK_REGISTRY["hello"] = create_hello_task()
    return TASK_REGISTRY


def get_task(task_name: str) -> Task:
    """Return a task from the registry by name."""

    if not TASK_REGISTRY:
        initialize_tasks()

    if task_name not in TASK_REGISTRY:
        raise KeyError(f"Unknown task: {task_name}")

    return TASK_REGISTRY[task_name]
