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


def create_hello_task() -> Task:
    def handler() -> None:
        print("Hello from the AI Operations Agent")

    return Task(name="hello", description="Print a friendly greeting", handler=handler)
