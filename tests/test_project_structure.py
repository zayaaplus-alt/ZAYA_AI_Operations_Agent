import importlib
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from zaya_ai_operations_agent.agent import Agent
from zaya_ai_operations_agent.api import app
from zaya_ai_operations_agent.cli import build_parser, run_task
from zaya_ai_operations_agent.config import Settings
from zaya_ai_operations_agent.memory import MemoryStore
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

    def test_agent_can_plan_execute_and_export_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "memory.json"
            memory_store = MemoryStore(memory_path)
            agent = Agent(memory_store=memory_store)

            plan = agent.plan("hello")
            record = agent.execute("hello")
            export_path = agent.export_history(Path(temp_dir) / "history.json")

            self.assertEqual(plan, ["hello"])
            self.assertEqual(record.task_name, "hello")
            self.assertEqual(record.status, "completed")
            self.assertEqual(len(agent.history()), 1)
            self.assertTrue(export_path.exists())
            self.assertIn("hello", export_path.read_text(encoding="utf-8"))

    def test_agent_cli_parser_supports_subcommands(self) -> None:
        parser = build_parser()
        agent_run_args = parser.parse_args(["agent", "run", "--task", "hello"])
        agent_history_args = parser.parse_args(["agent", "history"])
        agent_export_args = parser.parse_args(["agent", "export", "--output", "history.json"])

        self.assertEqual(agent_run_args.command, "agent")
        self.assertEqual(agent_run_args.agent_command, "run")
        self.assertEqual(agent_history_args.agent_command, "history")
        self.assertEqual(agent_export_args.agent_command, "export")

    def test_api_endpoints_return_expected_payloads(self) -> None:
        with TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "memory.json"
            settings = Settings(data_dir=Path(temp_dir), memory_file=memory_path)
            os.environ["MEMORY_FILE"] = str(memory_path)
            os.environ["API_KEY"] = "test-key"
            os.environ["API_ROLE"] = "admin"
            try:
                request = type("Request", (), {"headers": {"x-api-key": "test-key"}})()
                health_response = app.routes[0][2](request)
                tasks_response = app.routes[1][2](request)
                run_response = app.routes[2][2](type("Request", (), {"task_name": "hello"})(), request)
                history_response = app.routes[3][2](request)

                self.assertEqual(health_response["status"], "ok")
                self.assertGreaterEqual(len(tasks_response), 1)
                self.assertEqual(run_response["record"]["task_name"], "hello")
                self.assertGreaterEqual(len(history_response), 1)
            finally:
                os.environ.pop("MEMORY_FILE", None)
                os.environ.pop("API_KEY", None)
                os.environ.pop("API_ROLE", None)

    def test_api_rejects_missing_or_invalid_keys(self) -> None:
        os.environ["API_KEY"] = "secret"
        os.environ["API_ROLE"] = "viewer"
        try:
            request = type("Request", (), {"headers": {}})()
            with self.assertRaises(Exception):
                app.routes[0][2](request)
        finally:
            os.environ.pop("API_KEY", None)
            os.environ.pop("API_ROLE", None)

    def test_history_endpoints_and_admin_delete(self) -> None:
        with TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "memory.json"
            os.environ["MEMORY_FILE"] = str(memory_path)
            os.environ["API_KEY"] = "secret"
            os.environ["API_ROLE"] = "admin"
            try:
                request = type("Request", (), {"headers": {"x-api-key": "secret"}})()
                app.routes[2][2](type("Request", (), {"task_name": "hello"})(), request)
                history_response = app.routes[3][2](request)
                task_history_response = app.routes[4][2]("hello", request)
                delete_response = app.routes[5][2](request)

                self.assertGreaterEqual(len(history_response), 1)
                self.assertGreaterEqual(len(task_history_response), 1)
                self.assertEqual(delete_response["status"], "deleted")
            finally:
                os.environ.pop("MEMORY_FILE", None)
                os.environ.pop("API_KEY", None)
                os.environ.pop("API_ROLE", None)

    def test_viewer_cannot_execute_tasks(self) -> None:
        os.environ["API_KEY"] = "secret"
        os.environ["API_ROLE"] = "viewer"
        try:
            request = type("Request", (), {"headers": {"x-api-key": "secret"}})()
            with self.assertRaises(Exception):
                app.routes[2][2](type("Request", (), {"task_name": "hello"})(), request)
        finally:
            os.environ.pop("API_KEY", None)
            os.environ.pop("API_ROLE", None)

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
