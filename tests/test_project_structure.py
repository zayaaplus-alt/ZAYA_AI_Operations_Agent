import importlib
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from zaya_ai_operations_agent.cli import build_parser, run_task
from zaya_ai_operations_agent.config import Settings
from zaya_ai_operations_agent.scheduler import Scheduler
from zaya_ai_operations_agent.tasks import TASK_REGISTRY, get_task, initialize_tasks


class ProjectStructureTest(unittest.TestCase):
    def test_package_modules_are_importable(self) -> None:
        modules = [
            "zaya_ai_operations_agent.config",
            "zaya_ai_operations_agent.logging_utils",
            "zaya_ai_operations_agent.tasks",
            "zaya_ai_operations_agent.memory",
            "zaya_ai_operations_agent.cli",
        ]

        for module_name in modules:
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)

    def test_cli_parser_supports_run_command(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["run", "--task", "hello"])

        self.assertEqual(args.command, "run")
        self.assertEqual(args.task, "hello")

    def test_task_registry_contains_hello_task(self) -> None:
        initialize_tasks()

        self.assertIn("hello", TASK_REGISTRY)
        self.assertEqual(get_task("hello").name, "hello")

    def test_run_task_executes_hello_task(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = Settings(data_dir=Path(temp_dir), memory_file=Path(temp_dir) / "memory.json")
            output = StringIO()

            with redirect_stdout(output):
                run_task("hello", settings=settings)

            self.assertIn("Hello from the AI Operations Agent", output.getvalue())

    def test_run_task_executes_system_info_task(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = Settings(data_dir=Path(temp_dir), memory_file=Path(temp_dir) / "memory.json")
            output = StringIO()

            with redirect_stdout(output):
                run_task("system-info", settings=settings)

            self.assertIn("System Information", output.getvalue())
            self.assertIn("system:", output.getvalue())

    def test_settings_loads_values_from_env_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text(
                "OPENAI_API_KEY=sk-test\nLOG_LEVEL=DEBUG\nMEMORY_FILE=/tmp/custom-memory.json\n",
                encoding="utf-8",
            )

            settings = Settings(env_file=env_file)

            self.assertEqual(settings.openai_api_key, "sk-test")
            self.assertEqual(settings.log_level, "DEBUG")
            self.assertEqual(settings.memory_file, Path("/tmp/custom-memory.json"))

    def test_scheduler_supports_one_time_and_recurring_tasks(self) -> None:
        scheduler = Scheduler()
        one_time = scheduler.schedule_task("hello", run_once=True, start_at=datetime.now() - timedelta(seconds=1))
        recurring = scheduler.schedule_task("hello", interval_seconds=30, start_at=datetime.now() - timedelta(seconds=1))

        self.assertTrue(one_time.should_run())
        self.assertTrue(recurring.should_run())

        completed = scheduler.run_due_tasks(current_time=datetime.now())
        self.assertEqual(len(completed), 2)
        self.assertFalse(one_time.active)
        self.assertTrue(recurring.active)

    def test_cli_supports_schedule_and_list_commands(self) -> None:
        parser = build_parser()
        schedule_args = parser.parse_args(["schedule", "--task", "hello", "--once"])
        list_args = parser.parse_args(["list-scheduled"])

        self.assertEqual(schedule_args.command, "schedule")
        self.assertEqual(schedule_args.task, "hello")
        self.assertTrue(schedule_args.once)
        self.assertEqual(list_args.command, "list-scheduled")

    def test_settings_uses_defaults_when_env_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env"
            env_file.write_text("", encoding="utf-8")

            original_env = os.environ.copy()
            os.environ.clear()
            try:
                settings = Settings(data_dir=Path(temp_dir), memory_file=None, env_file=env_file)
            finally:
                os.environ.clear()
                os.environ.update(original_env)

            self.assertIsNone(settings.openai_api_key)
            self.assertEqual(settings.log_level, "INFO")
            self.assertEqual(settings.memory_file, Path(temp_dir) / "memory.json")


if __name__ == "__main__":
    unittest.main()
