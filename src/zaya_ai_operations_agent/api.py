from __future__ import annotations

import os
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

        def delete(self, path: str):
            def decorator(func):
                self.routes.append(("DELETE", path, func))
                return func

            return decorator

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

from .agent import Agent
from .config import Settings
from .dashboard import build_dashboard_html
from .memory import MemoryStore
from .orchestrator import AgentManager
from .scheduler import Scheduler
from .tasks import TASK_REGISTRY, initialize_tasks


ALLOWED_ROLES = {"admin", "operator", "viewer"}
ROLE_PERMISSIONS = {
    "admin": {"health", "tasks", "tasks/run", "history"},
    "operator": {"health", "tasks", "tasks/run", "history"},
    "viewer": {"health", "tasks", "history"},
}


class TaskRunRequest(BaseModel):
    task_name: str


app = FastAPI(title="ZAYA AI Operations Agent API", version="0.1.0")


def _get_request_context(request: Any = None) -> tuple[str, str]:
    settings = Settings()
    api_key = os.environ.get("API_KEY") or settings.openai_api_key or None
    role = os.environ.get("API_ROLE") or "viewer"
    if role not in ALLOWED_ROLES:
        role = "viewer"
    if request is not None:
        headers = getattr(request, "headers", {}) or {}
        provided_key = headers.get("x-api-key") if hasattr(headers, "get") else None
        if provided_key is None:
            provided_key = headers.get("X-API-Key") if hasattr(headers, "get") else None
        if provided_key != api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
    elif api_key is None:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key, role


def require_access(path: str, request: Any = None) -> None:
    _, role = _get_request_context(request)
    if path not in ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(status_code=403, detail="Access denied")


@app.get("/")
def dashboard_root(request: Any = None) -> str:
    return _build_dashboard_html(request)


@app.get("/dashboard")
def dashboard(request: Any = None) -> str:
    return _build_dashboard_html(request)


@app.get("/health")
def health(request: Any = None) -> dict[str, str]:
    require_access("health", request)
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks(request: Any = None) -> list[dict[str, str]]:
    require_access("tasks", request)
    initialize_tasks()
    return [
        {"name": name, "description": task.description}
        for name, task in sorted(TASK_REGISTRY.items())
    ]


@app.post("/tasks/run")
def run_task(request: TaskRunRequest, auth_request: Any = None) -> dict[str, Any]:
    require_access("tasks/run", auth_request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)

    try:
        plan = agent.plan(request.task_name)
        record = agent.execute(request.task_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {"plan": plan, "record": record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "status": record.status, "details": record.details, "executed_at": record.executed_at}}


@app.get("/agents")
def list_agents(request: Any = None) -> list[dict[str, str]]:
    require_access("health", request)
    return [
        {"name": "PlannerAgent", "role": "planner"},
        {"name": "ExecutorAgent", "role": "executor"},
        {"name": "ReviewerAgent", "role": "reviewer"},
    ]


@app.post("/agents/run")
def run_agent(request: Any = None, auth_request: Any = None) -> dict[str, Any]:
    require_access("tasks/run", auth_request or request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = AgentManager(memory_store=memory_store)
    payload = getattr(request, "json", lambda: {})() if hasattr(request, "json") else {}
    task_name = payload.get("task_name", "hello")
    user_role = payload.get("user_role", "viewer")
    result = manager.run(task_name, user_role=user_role)
    return {
        "planner_plan": result.planner_plan,
        "executor_result": result.executor_result,
        "reviewer_result": result.reviewer_result,
        "status": result.status,
        "executed_at": result.executed_at,
    }


@app.get("/history")
def history(request: Any = None) -> list[dict[str, Any]]:
    require_access("history", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)
    return [record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "status": record.status, "user_role": getattr(record, "user_role", "viewer"), "execution_duration_seconds": getattr(record, "execution_duration_seconds", 0.0), "details": record.details, "executed_at": record.executed_at} for record in agent.history()]


@app.get("/history/{task_name}")
def history_for_task(task_name: str, request: Any = None) -> list[dict[str, Any]]:
    require_access("history", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)
    return [record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "status": record.status, "user_role": getattr(record, "user_role", "viewer"), "execution_duration_seconds": getattr(record, "execution_duration_seconds", 0.0), "details": record.details, "executed_at": record.executed_at} for record in agent.history_for_task(task_name)]


@app.delete("/history")
def delete_history(request: Any = None) -> dict[str, str]:
    _, role = _get_request_context(request)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete history")
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)
    agent.clear_history()
    return {"status": "deleted"}


def _build_dashboard_html(request: Any = None) -> str:
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    agent = Agent(memory_store=memory_store)
    initialize_tasks()
    scheduler = Scheduler()
    scheduled_tasks = [
        {"task_name": item.task_name, "next_run_at": item.next_run_at.isoformat(), "active": item.active}
        for item in scheduler.list_scheduled()
    ]
    history = [
        {
            "executed_at": record.executed_at,
            "task_name": record.task_name,
            "status": record.status,
        }
        for record in agent.history()[-5:]
    ]
    return build_dashboard_html(
        {
            "status": "ok",
            "project_name": settings.project_name,
            "log_level": settings.log_level,
            "memory_file": str(settings.memory_file),
            "tasks": [
                {"name": name, "description": task.description}
                for name, task in sorted(TASK_REGISTRY.items())
            ],
            "scheduled_tasks": scheduled_tasks,
            "history": history,
        }
    )
