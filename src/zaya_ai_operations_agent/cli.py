from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .agent import Agent
from .config import Settings
from .logging_utils import get_logger
from .memory import MemoryStore
from .scheduler import Scheduler
from .tasks import Task, get_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zaya-ai-operations-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a registered task")
    run_parser.add_argument("--task", required=True, help="Name of the task to run")

    schedule_parser = subparsers.add_parser("schedule", help="Schedule a task")
    schedule_parser.add_argument("--task", required=True, help="Name of the task to schedule")
    schedule_parser.add_argument("--once", action="store_true", help="Run the task once")
    schedule_parser.add_argument("--interval", type=int, default=None, help="Recurring interval in seconds")
    schedule_parser.add_argument("--minutes", type=int, default=None, help="Recurring interval in minutes")

    list_scheduled_parser = subparsers.add_parser("list-scheduled", help="List scheduled tasks")

    agent_parser = subparsers.add_parser("agent", help="Run the AI agent framework")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    agent_run_parser = agent_subparsers.add_parser("run", help="Ask the agent to execute a task")
    agent_run_parser.add_argument("--task", required=True, help="Name of the task to execute")

    agent_history_parser = agent_subparsers.add_parser("history", help="Show agent execution history")
    agent_export_parser = agent_subparsers.add_parser("export", help="Export agent execution history")
    agent_export_parser.add_argument("--output", required=True, help="Path to write the JSON export")
    return parser


def run_task(task_name: str, settings: Optional[Settings] = None) -> None:
    settings = settings or Settings()
    logger = get_logger("zaya_ai_operations_agent.cli", settings.log_level)
    memory = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())

    logger.info("Starting task: %s", task_name)

    task: Task = get_task(task_name)
    task.run()
    memory.set("last_task", task_name)
    logger.info("Completed task: %s", task_name)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        run_task(args.task)
    elif args.command == "schedule":
        scheduler = Scheduler()
        interval_seconds = args.interval
        if args.minutes is not None:
            interval_seconds = args.minutes * 60
        if args.once:
            scheduler.schedule_task(args.task, run_once=True)
        else:
            scheduler.schedule_task(args.task, interval_seconds=interval_seconds)
        print(f"Scheduled task: {args.task}")
    elif args.command == "list-scheduled":
        scheduler = Scheduler()
        scheduled = scheduler.list_scheduled()
        if not scheduled:
            print("No scheduled tasks")
        else:
            for item in scheduled:
                print(f"{item.task_name} -> active={item.active} next_run={item.next_run_at}")
    elif args.command == "agent":
        settings = Settings()
        memory_store = MemoryStore(settings.memory_file or Path("~/.zaya_ai_operations_agent/memory.json").expanduser())
        agent = Agent(memory_store=memory_store)

        if args.agent_command == "run":
            plan = agent.plan(args.task)
            print(f"Plan: {plan}")
            record = agent.execute(args.task)
            print(f"Executed {record.task_name} ({record.status})")
        elif args.agent_command == "history":
            for record in agent.history():
                print(f"{record.executed_at} | {record.task_name} | {record.status}")
        elif args.agent_command == "export":
            exported_path = agent.export_history(Path(args.output))
            print(f"Exported history to {exported_path}")


if __name__ == "__main__":
    main()
