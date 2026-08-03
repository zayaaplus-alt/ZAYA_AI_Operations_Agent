from __future__ import annotations

import os
import subprocess
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from .logging_utils import get_logger
from .memory import MemoryStore
from .tasks import get_task


@dataclass(slots=True)
class ToolResult:
    name: str
    status: str
    output: str
    executed_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    required_role: str = "operator"
    handler: Optional[Callable[[dict[str, Any]], ToolResult]] = None

    def execute(self, arguments: Optional[dict[str, Any]] = None) -> ToolResult:
        if self.handler is None:
            raise ValueError(f"Tool '{self.name}' has no handler")
        return self.handler(arguments or {})


class ToolRegistry:
    """Registry for dynamically registering and discovering tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._audit_log: list[dict[str, Any]] = []

    def register(self, tool: Tool) -> Tool:
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def audit(self, tool_name: str, role: str, status: str, details: str) -> None:
        self._audit_log.append({"tool_name": tool_name, "role": role, "status": status, "details": details, "executed_at": datetime.now().isoformat()})

    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)


class ToolExecutionManager:
    """Executes tools with permission checks and audit logging."""

    def __init__(self, registry: Optional[ToolRegistry] = None, memory_store: Optional[MemoryStore] = None) -> None:
        self.registry = registry or ToolRegistry()
        self.memory_store = memory_store
        self.logger = get_logger("zaya_ai_operations_agent.tools")

    def _get_memory(self) -> MemoryStore:
        if self.memory_store is None:
            self.memory_store = MemoryStore(Path("~/.zaya_ai_operations_agent/tools.json").expanduser())
        return self.memory_store

    def execute(self, tool_name: str, arguments: Optional[dict[str, Any]] = None, role: str = "viewer") -> ToolResult:
        tool = self.registry.get(tool_name)
        role_hierarchy = {"viewer": 0, "operator": 1, "admin": 2}
        if role_hierarchy.get(role, 0) < role_hierarchy.get(tool.required_role, 0):
            raise PermissionError(f"Role '{role}' is not allowed to execute tool '{tool_name}'")
        try:
            result = tool.execute(arguments or {})
            self.registry.audit(tool_name, role, result.status, result.output)
            self._get_memory().set(f"tool:{tool_name}", {"status": result.status, "output": result.output, "executed_at": result.executed_at, "role": role})
            return result
        except Exception as exc:
            self.registry.audit(tool_name, role, "failed", str(exc))
            raise


def build_builtin_tools() -> ToolRegistry:
    registry = ToolRegistry()

    def file_operation(arguments: dict[str, Any]) -> ToolResult:
        path = arguments.get("path", "")
        operation = arguments.get("operation", "read")
        try:
            path_obj = Path(path)
            if operation == "read":
                content = path_obj.read_text(encoding="utf-8") if path_obj.exists() else ""
                return ToolResult(name="file-read", status="success", output=content, executed_at=datetime.now().isoformat())
            if operation == "write":
                path_obj.write_text(arguments.get("content", ""), encoding="utf-8")
                return ToolResult(name="file-write", status="success", output=f"Wrote {path_obj}", executed_at=datetime.now().isoformat())
            return ToolResult(name="file-op", status="failed", output="Unsupported file operation", executed_at=datetime.now().isoformat())
        except Exception as exc:
            return ToolResult(name="file-op", status="failed", output=str(exc), executed_at=datetime.now().isoformat())

    def http_request(arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url", "")
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                body = response.read().decode("utf-8", errors="ignore")
                return ToolResult(name="http-request", status="success", output=body, executed_at=datetime.now().isoformat(), metadata={"url": url})
        except Exception as exc:
            return ToolResult(name="http-request", status="failed", output=str(exc), executed_at=datetime.now().isoformat(), metadata={"url": url})

    def shell_command(arguments: dict[str, Any]) -> ToolResult:
        command = arguments.get("command", "")
        try:
            completed = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10, check=False)
            output = completed.stdout or completed.stderr or ""
            return ToolResult(name="shell-command", status="success" if completed.returncode == 0 else "failed", output=output, executed_at=datetime.now().isoformat())
        except Exception as exc:
            return ToolResult(name="shell-command", status="failed", output=str(exc), executed_at=datetime.now().isoformat())

    def email_placeholder(arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(name="email", status="success", output="Email sending is not implemented in this environment", executed_at=datetime.now().isoformat(), metadata={"to": arguments.get("to", "")})

    def webhook_sender(arguments: dict[str, Any]) -> ToolResult:
        url = arguments.get("url", "")
        payload = arguments.get("payload", {})
        try:
            data = str(payload).encode("utf-8")
            request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8", errors="ignore")
                return ToolResult(name="webhook", status="success", output=body, executed_at=datetime.now().isoformat(), metadata={"url": url})
        except Exception as exc:
            return ToolResult(name="webhook", status="failed", output=str(exc), executed_at=datetime.now().isoformat(), metadata={"url": url})

    registry.register(Tool(name="file-ops", description="Read or write a file", required_role="operator", handler=file_operation))
    registry.register(Tool(name="http-request", description="Perform an HTTP GET request", required_role="operator", handler=http_request))
    registry.register(Tool(name="shell-command", description="Execute a restricted shell command", required_role="admin", handler=shell_command))
    registry.register(Tool(name="email", description="Placeholder email sender", required_role="operator", handler=email_placeholder))
    registry.register(Tool(name="webhook", description="Send an HTTP POST webhook", required_role="operator", handler=webhook_sender))
    return registry
