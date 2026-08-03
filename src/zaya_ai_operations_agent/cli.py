from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .config import Settings
from .logging_utils import get_logger
from .memory import MemoryStore
from .tasks import Task, get_task


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zaya-ai-operations-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a registered task")
    run_parser.add_argument("--task", required=True, help="Name of the task to run")
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


if __name__ == "__main__":
    main()
