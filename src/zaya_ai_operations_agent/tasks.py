from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
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


def _discover_plugins() -> list[Callable[[dict[str, Task]], None]]:
    plugin_package = import_module("zaya_ai_operations_agent.tasks_plugins")
    plugin_modules = [
        import_module(f"{plugin_package.__name__}.{path.stem}")
        for path in Path(plugin_package.__file__).parent.glob("*.py")
        if path.name != "__init__.py"
    ]

    register_functions: list[Callable[[dict[str, Task]], None]] = []
    for module in plugin_modules:
        register_func = getattr(module, "register_" + module.__name__.split(".")[-1] + "_task", None)
        if callable(register_func):
            register_functions.append(register_func)

    return register_functions


def initialize_tasks() -> dict[str, Task]:
    """Populate the task registry with built-in tasks discovered from plugins."""

    TASK_REGISTRY.clear()
    for register_task in _discover_plugins():
        register_task(TASK_REGISTRY)
    return TASK_REGISTRY


def get_task(task_name: str) -> Task:
    """Return a task from the registry by name."""

    if not TASK_REGISTRY:
        initialize_tasks()

    if task_name not in TASK_REGISTRY:
        raise KeyError(f"Unknown task: {task_name}")

    return TASK_REGISTRY[task_name]
