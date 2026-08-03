from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:  # pragma: no cover - exercised when dependency is unavailable
    class BaseModel:  # type: ignore[override]
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    class FastAPI:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs
            self.routes: list[tuple[str, str, Any]] = []

        def get(self, path: str):
            def decorator(func):
                self.routes.append(("GET", path, func))
                return func

            return decorator

        def post(self, path: str):
            def decorator(func):
                self.routes.append(("POST", path, func))
                return func

            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

from .agent import Agent
from .config import Settings
from .memory import MemoryStore
from .tasks import TASK_REGISTRY, initialize_tasks


class TaskRunRequest(BaseModel):
    task_name: str


app = FastAPI(title="ZAYA AI Operations Agent API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks() -> list[dict[str, str]]:
    initialize_tasks()
    return [
        {"name": name, "description": task.description}
        for name, task in sorted(TASK_REGISTRY.items())
    ]


@app.post("/tasks/run")
def run_task(request: TaskRunRequest) -> dict[str, Any]:
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)

    try:
        plan = agent.plan(request.task_name)
        record = agent.execute(request.task_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"plan": plan, "record": record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "status": record.status, "details": record.details, "executed_at": record.executed_at}}


@app.get("/history")
def history() -> list[dict[str, Any]]:
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)
    return [record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "status": record.status, "details": record.details, "executed_at": record.executed_at} for record in agent.history()]
