from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

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


if __name__ == "__main__":
    main()
