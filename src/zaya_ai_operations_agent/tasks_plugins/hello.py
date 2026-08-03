from __future__ import annotations

from ..tasks import Task


def register_hello_task(registry: dict[str, Task]) -> None:
    def handler() -> None:
        print("Hello from the AI Operations Agent")

    registry["hello"] = Task(
        name="hello",
        description="Print a friendly greeting",
        handler=handler,
    )
