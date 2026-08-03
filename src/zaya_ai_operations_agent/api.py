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
from .knowledge import KnowledgeManager
from .llm import LLMProviderFactory
from .memory import MemoryStore
from .orchestrator import AgentManager
from .scheduler import Scheduler
from .tasks import TASK_REGISTRY, initialize_tasks
from .tools import ToolExecutionManager, build_builtin_tools
from .workflows import RetryPolicy, Workflow, WorkflowManager, WorkflowStep


ALLOWED_ROLES = {"admin", "operator", "viewer"}
ROLE_PERMISSIONS = {
    "admin": {"health", "tasks", "tasks/run", "history", "workflows", "workflows/run", "knowledge", "knowledge/upload", "knowledge/search", "knowledge/documents"},
    "operator": {"health", "tasks", "tasks/run", "history", "workflows", "workflows/run", "knowledge", "knowledge/upload", "knowledge/search", "knowledge/documents"},
    "viewer": {"health", "tasks", "history", "workflows", "knowledge", "knowledge/search", "knowledge/documents"},
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


def _get_json_payload(request: Any = None) -> dict[str, Any]:
    if request is None:
        return {}
    if hasattr(request, "json"):
        json_payload = getattr(request, "json")
        if callable(json_payload):
            payload = json_payload()
            if isinstance(payload, dict):
                return payload
        return {}
    return getattr(request, "__dict__", {})


@app.get("/workflows")
def list_workflows(request: Any = None) -> list[dict[str, Any]]:
    require_access("workflows", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = WorkflowManager(memory_store=memory_store)
    workflows = manager.list_workflows()
    return [
        {
            "name": workflow.name,
            "steps": [{"task_name": step.task_name, "condition": step.condition} for step in workflow.steps],
            "retry_policy": {"max_retries": workflow.retry_policy.max_retries, "retry_delay_seconds": workflow.retry_policy.retry_delay_seconds},
        }
        for workflow in workflows
    ]


@app.post("/workflows")
def create_workflow(request: Any = None) -> dict[str, Any]:
    require_access("workflows", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = WorkflowManager(memory_store=memory_store)
    payload = _get_json_payload(request)
    steps = [WorkflowStep(task_name=step.get("task_name", "hello"), condition=step.get("condition", "always")) for step in payload.get("steps", [])]
    retry_policy = RetryPolicy(**payload.get("retry_policy", {})) if payload.get("retry_policy") else RetryPolicy()
    workflow = Workflow(name=payload.get("name", "new-workflow"), steps=steps, retry_policy=retry_policy)
    created = manager.create_workflow(workflow)
    return {
        "name": created.name,
        "steps": [{"task_name": step.task_name, "condition": step.condition} for step in created.steps],
        "retry_policy": {"max_retries": created.retry_policy.max_retries, "retry_delay_seconds": created.retry_policy.retry_delay_seconds},
    }


@app.post("/workflows/run")
def run_workflow(request: Any = None) -> dict[str, Any]:
    require_access("workflows/run", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = WorkflowManager(memory_store=memory_store)
    payload = _get_json_payload(request)
    workflow_name = payload.get("workflow_name") or payload.get("name") or "demo-workflow"
    user_role = payload.get("user_role", "viewer")
    result = manager.run_workflow(workflow_name, user_role=user_role)
    return {
        "workflow_name": result.workflow_name,
        "status": result.status,
        "step_results": result.step_results,
        "executed_at": result.executed_at,
    }


@app.get("/workflows/history")
def workflow_history(request: Any = None) -> list[dict[str, Any]]:
    require_access("history", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = WorkflowManager(memory_store=memory_store)
    return [record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "status": record.status, "user_role": getattr(record, "user_role", "viewer"), "execution_duration_seconds": getattr(record, "execution_duration_seconds", 0.0), "details": record.details, "executed_at": record.executed_at} for record in manager.history()]


@app.post("/knowledge/upload")
def upload_knowledge(request: Any = None) -> dict[str, Any]:
    require_access("knowledge/upload", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = KnowledgeManager(memory_store=memory_store)
    payload = _get_json_payload(request)
    path = payload.get("path")
    title = payload.get("title")
    metadata = payload.get("metadata") or {}
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")
    document = manager.ingest_document(path, title=title, metadata=metadata)
    return {"id": document.id, "title": document.title, "file_type": document.file_type, "created_at": document.created_at}


@app.get("/knowledge/search")
def search_knowledge(request: Any = None) -> list[dict[str, Any]]:
    require_access("knowledge/search", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = KnowledgeManager(memory_store=memory_store)
    payload = _get_json_payload(request)
    query = payload.get("query") or ""
    return manager.search(query, top_k=payload.get("top_k", 5))


@app.get("/knowledge/documents")
def list_knowledge_documents(request: Any = None) -> list[dict[str, Any]]:
    require_access("knowledge/documents", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = KnowledgeManager(memory_store=memory_store)
    return manager.list_documents()


@app.get("/llm/providers")
def list_llm_providers(request: Any = None) -> list[dict[str, str]]:
    require_access("knowledge", request)
    settings = Settings()
    provider_settings = LLMProviderFactory.load_settings(settings)
    return [
        {"name": "mock", "active": provider_settings.provider == "mock"},
        {"name": "openai", "active": provider_settings.provider == "openai"},
        {"name": "anthropic", "active": provider_settings.provider == "anthropic"},
        {"name": "gemini", "active": provider_settings.provider == "gemini"},
        {"name": "ollama", "active": provider_settings.provider == "ollama"},
    ]


@app.get("/tools")
def list_tools(request: Any = None) -> list[dict[str, Any]]:
    require_access("knowledge", request)
    registry = build_builtin_tools()
    return [{"name": tool.name, "description": tool.description, "required_role": tool.required_role} for tool in registry.list_tools()]


@app.post("/tools/run")
def run_tool(request: Any = None, auth_request: Any = None) -> dict[str, Any]:
    require_access("knowledge", auth_request or request)
    payload = _get_json_payload(request)
    tool_name = payload.get("tool_name")
    arguments = payload.get("arguments", {}) or {}
    role = payload.get("role", "viewer")
    manager = ToolExecutionManager(registry=build_builtin_tools())
    result = manager.execute(tool_name, arguments=arguments, role=role)
    return {"name": result.name, "status": result.status, "output": result.output, "executed_at": result.executed_at, "metadata": result.metadata}


@app.delete("/knowledge/document/{document_id}")
def delete_knowledge_document(document_id: str, request: Any = None) -> dict[str, Any]:
    require_access("knowledge/documents", request)
    settings = Settings()
    memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
    manager = KnowledgeManager(memory_store=memory_store)
    manager.delete_document(document_id)
    return {"status": "deleted", "id": document_id}


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
    workflow_manager = WorkflowManager(memory_store=memory_store)
    workflows = [
        {
            "name": workflow.name,
            "steps": [step.task_name for step in workflow.steps],
        }
        for workflow in workflow_manager.list_workflows()
    ]
    knowledge_manager = KnowledgeManager(memory_store=memory_store)
    knowledge_documents = knowledge_manager.list_documents()
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
            "workflows": workflows,
            "knowledge_documents": knowledge_documents,
        }
    )
