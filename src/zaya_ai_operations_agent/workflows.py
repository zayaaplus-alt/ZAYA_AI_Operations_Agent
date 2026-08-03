from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .agent import Agent, ExecutionRecord
from .llm import LLMProviderFactory
from .memory import MemoryStore
from .orchestrator import AgentManager
from .scheduler import Scheduler
from .tasks import Task, get_task
from .tools import ToolExecutionManager, build_builtin_tools
from .workspaces import UserManager, WorkspaceManager


@dataclass(slots=True)
class RetryPolicy:
    """Retry policy for workflow step execution."""

    max_retries: int = 0
    retry_delay_seconds: int = 0


@dataclass(slots=True)
class WorkflowStep:
    """A single step in a workflow."""

    task_name: str
    condition: str = "always"


@dataclass(slots=True)
class Workflow:
    """A collection of ordered workflow steps with optional retry policy."""

    name: str
    steps: list[WorkflowStep]
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)


@dataclass(slots=True)
class WorkflowExecutionResult:
    """Execution result for a workflow."""

    workflow_name: str
    status: str
    step_results: list[dict[str, Any]]
    executed_at: str


class WorkflowManager:
    """Manages workflow definitions and their executions."""

    def __init__(self, memory_store: Optional[MemoryStore] = None, scheduler: Optional[Scheduler] = None, agent_manager: Optional[AgentManager] = None, llm_provider: Optional[Any] = None) -> None:
        self.memory_store = memory_store
        self.scheduler = scheduler or Scheduler()
        self.agent_manager = agent_manager
        self.tool_manager = ToolExecutionManager(registry=build_builtin_tools())
        self.user_manager = UserManager(memory_store=memory_store)
        self.workspace_manager = WorkspaceManager(memory_store=memory_store)
        self._workflows: dict[str, Workflow] = {}
        self.agent = Agent(memory_store=memory_store, llm_provider=llm_provider or LLMProviderFactory.create())

    def _get_memory(self) -> MemoryStore:
        if self.memory_store is None:
            self.memory_store = MemoryStore(Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
        return self.memory_store

    def create_workflow(self, workflow: Workflow) -> Workflow:
        self._workflows[workflow.name] = workflow
        memory = self._get_memory()
        workflows_data = memory.get("workflows", [])
        workflows_data.append(asdict(workflow))
        memory.set("workflows", workflows_data)
        return workflow

    def get_workflow(self, name: str) -> Optional[Workflow]:
        if name in self._workflows:
            return self._workflows[name]
        memory = self._get_memory()
        stored_workflows = memory.get("workflows", [])
        for entry in stored_workflows:
            if entry.get("name") == name:
                workflow = Workflow(
                    name=entry["name"],
                    steps=[WorkflowStep(**step) for step in entry.get("steps", [])],
                    retry_policy=RetryPolicy(**entry.get("retry_policy", {})),
                )
                self._workflows[name] = workflow
                return workflow
        return None

    def list_workflows(self) -> list[Workflow]:
        memory = self._get_memory()
        stored_workflows = memory.get("workflows", [])
        workflows = [
            Workflow(
                name=entry["name"],
                steps=[WorkflowStep(**step) for step in entry.get("steps", [])],
                retry_policy=RetryPolicy(**entry.get("retry_policy", {})),
            )
            for entry in stored_workflows
        ]
        self._workflows = {workflow.name: workflow for workflow in workflows}
        return workflows

    def run_workflow(self, workflow_name: str, user_role: str = "viewer") -> WorkflowExecutionResult:
        workflow = self.get_workflow(workflow_name)
        if workflow is None:
            raise KeyError(f"Unknown workflow: {workflow_name}")

        self.scheduler.run_due_tasks()
        step_results: list[dict[str, Any]] = []
        status = "success"
        for step in workflow.steps:
            should_run = self._should_run_step(step.condition, step_results)
            if not should_run:
                step_results.append({"task_name": step.task_name, "status": "skipped", "condition": step.condition})
                continue

            attempt = 0
            while True:
                try:
                    task: Task = get_task(step.task_name)
                    task.run()
                    step_results.append({"task_name": step.task_name, "status": "completed", "condition": step.condition})
                    break
                except Exception as exc:
                    if attempt >= workflow.retry_policy.max_retries:
                        status = "failed"
                        step_results.append({"task_name": step.task_name, "status": "failed", "condition": step.condition, "error": str(exc)})
                        break
                    attempt += 1

            if status == "failed":
                break

        record = ExecutionRecord(
            task_name=workflow_name,
            executed_at=datetime.now().isoformat(),
            status=status,
            user_role=user_role,
            details=f"Workflow {workflow_name} completed with {len(step_results)} steps",
        )
        self.agent._history.append(record)
        if self.agent_manager is not None:
            self.agent_manager.agent._history.append(record)
            self.agent_manager.agent._get_memory().set("agent_history", self.agent_manager.agent._history if False else self.agent_manager.agent._get_memory().get("agent_history", []))
        memory = self._get_memory()
        history_data = memory.get("agent_history", [])
        history_data.append(asdict(record))
        memory.set("agent_history", history_data)
        return WorkflowExecutionResult(
            workflow_name=workflow_name,
            status=status,
            step_results=step_results,
            executed_at=datetime.now().isoformat(),
        )

    def history(self) -> list[ExecutionRecord]:
        return self.agent.history()

    def _should_run_step(self, condition: str, step_results: list[dict[str, Any]]) -> bool:
        if condition == "always":
            return True
        if condition == "success" and step_results:
            return all(result.get("status") == "completed" for result in step_results)
        if condition == "failure" and step_results:
            return any(result.get("status") == "failed" for result in step_results)
        return False
