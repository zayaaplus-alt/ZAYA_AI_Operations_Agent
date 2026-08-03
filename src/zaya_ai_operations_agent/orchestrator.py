from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .agent import Agent, ExecutionRecord
from .memory import MemoryStore
from .tasks import Task, get_task


@dataclass(slots=True)
class AgentRunResult:
    planner_plan: list[str]
    executor_result: str
    reviewer_result: str
    status: str
    executed_at: str


class PlannerAgent:
    """Creates a plan from a task name."""

    def plan(self, task_name: str) -> list[str]:
        return [task_name]


class ExecutorAgent:
    """Executes a task from the registry."""

    def execute(self, task_name: str) -> str:
        task: Task = get_task(task_name)
        task.run()
        return f"Executed {task_name}"


class ReviewerAgent:
    """Validates that the execution succeeded."""

    def review(self, task_name: str, execution_result: str) -> str:
        if execution_result.startswith("Executed"):
            return f"Review passed for {task_name}"
        return f"Review failed for {task_name}"


class AgentManager:
    """Coordinates planner, executor, and reviewer agents."""

    def __init__(self, memory_store: Optional[MemoryStore] = None) -> None:
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.reviewer = ReviewerAgent()
        self.agent = Agent(memory_store=memory_store)

    def run(self, task_name: str, user_role: str = "viewer") -> AgentRunResult:
        plan = self.planner.plan(task_name)
        execution_result = self.executor.execute(task_name)
        review_result = self.reviewer.review(task_name, execution_result)
        status = "success" if review_result.startswith("Review passed") else "failed"
        record = ExecutionRecord(
            task_name=task_name,
            executed_at=datetime.now().isoformat(),
            status=status,
            user_role=user_role,
            details=f"{execution_result}; {review_result}",
        )
        self.agent._history.append(record)
        memory = self.agent._get_memory()
        history_data = memory.get("agent_history", [])
        history_data.append(record.__dict__ if hasattr(record, "__dict__") else {"task_name": record.task_name, "executed_at": record.executed_at, "status": record.status, "user_role": record.user_role, "execution_duration_seconds": record.execution_duration_seconds, "details": record.details})
        memory.set("agent_history", history_data)
        return AgentRunResult(
            planner_plan=plan,
            executor_result=execution_result,
            reviewer_result=review_result,
            status=status,
            executed_at=record.executed_at,
        )
