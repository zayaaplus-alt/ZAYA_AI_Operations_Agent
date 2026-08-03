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
from zaya_ai_operations_agent.orchestrator import AgentManager
from zaya_ai_operations_agent.scheduler import Scheduler
from zaya_ai_operations_agent.tasks import TASK_REGISTRY, get_task, initialize_tasks
from zaya_ai_operations_agent.workflows import RetryPolicy, Workflow, WorkflowManager, WorkflowStep


class ProjectStructureTest(unittest.TestCase):
    def _match_route(self, route_path: str, requested_path: str) -> bool:
        route_parts = route_path.split("/")
        requested_parts = requested_path.split("/")
        if len(route_parts) != len(requested_parts):
            return False
        for route_part, requested_part in zip(route_parts, requested_parts):
            if route_part.startswith("{") and route_part.endswith("}"):
                continue
            if route_part != requested_part:
                return False
        return True

    def _get_route(self, method: str, path: str):
        for route_method, route_path, handler in app.routes:
            if route_method == method and self._match_route(route_path, path):
                return handler
        self.fail(f"Route {method} {path} not found")

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
                health_response = self._get_route("GET", "/health")(request)
                tasks_response = self._get_route("GET", "/tasks")(request)
                run_response = self._get_route("POST", "/tasks/run")(type("Request", (), {"task_name": "hello"})(), request)
                history_response = self._get_route("GET", "/history")(request)

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
                self._get_route("GET", "/health")(request)
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
                self._get_route("POST", "/tasks/run")(type("Request", (), {"task_name": "hello"})(), request)
                history_response = self._get_route("GET", "/history")(request)
                task_history_response = self._get_route("GET", "/history/hello")("hello", request)
                delete_response = self._get_route("DELETE", "/history")(request)

                self.assertGreaterEqual(len(history_response), 1)
                self.assertGreaterEqual(len(task_history_response), 1)
                self.assertEqual(delete_response["status"], "deleted")
            finally:
                os.environ.pop("MEMORY_FILE", None)
                os.environ.pop("API_KEY", None)
                os.environ.pop("API_ROLE", None)

    def test_dashboard_routes_return_html(self) -> None:
        root_response = self._get_route("GET", "/")()
        dashboard_response = self._get_route("GET", "/dashboard")()

        self.assertIn("ZAYA AI Operations Agent Dashboard", root_response)
        self.assertIn("ZAYA AI Operations Agent Dashboard", dashboard_response)

    def test_agent_manager_runs_planner_executor_and_reviewer(self) -> None:
        with TemporaryDirectory() as temp_dir:
            memory_store = MemoryStore(Path(temp_dir) / "memory.json")
            manager = AgentManager(memory_store=memory_store)
            result = manager.run("hello", user_role="operator")

            self.assertEqual(result.planner_plan, ["hello"])
            self.assertEqual(result.status, "success")
            self.assertIn("Review passed", result.reviewer_result)
            self.assertGreaterEqual(len(manager.agent.history()), 1)

    def test_agents_api_endpoints(self) -> None:
        os.environ["API_KEY"] = "secret"
        os.environ["API_ROLE"] = "admin"
        try:
            request = type("Request", (), {"headers": {"x-api-key": "secret"}, "json": lambda self: {"task_name": "hello", "user_role": "admin"}})()
            agents_response = self._get_route("GET", "/agents")(request)
            run_response = self._get_route("POST", "/agents/run")(request)

            self.assertGreaterEqual(len(agents_response), 3)
            self.assertEqual(run_response["status"], "success")
        finally:
            os.environ.pop("API_KEY", None)
            os.environ.pop("API_ROLE", None)

    def test_workflow_manager_runs_multi_step_workflow_with_retries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            memory_store = MemoryStore(Path(temp_dir) / "memory.json")
            manager = WorkflowManager(memory_store=memory_store)
            workflow = Workflow(
                name="demo-workflow",
                steps=[
                    WorkflowStep(task_name="hello", condition="always"),
                    WorkflowStep(task_name="system-info", condition="success"),
                ],
                retry_policy=RetryPolicy(max_retries=1),
            )
            manager.create_workflow(workflow)
            result = manager.run_workflow("demo-workflow", user_role="operator")

            self.assertEqual(result.workflow_name, "demo-workflow")
            self.assertEqual(result.status, "success")
            self.assertEqual(len(result.step_results), 2)
            self.assertIsNotNone(manager.get_workflow("demo-workflow"))
            self.assertGreaterEqual(len(manager.history()), 1)

    def test_workflow_api_endpoints(self) -> None:
        os.environ["API_KEY"] = "secret"
        os.environ["API_ROLE"] = "admin"
        try:
            request = type("Request", (), {"headers": {"x-api-key": "secret"}, "json": lambda self: {"name": "workflow-api", "steps": [{"task_name": "hello", "condition": "always"}], "retry_policy": {"max_retries": 1}}})()
            workflows_response = self._get_route("GET", "/workflows")(request)
            create_response = self._get_route("POST", "/workflows")(request)
            run_response = self._get_route("POST", "/workflows/run")(request)
            workflow_history_response = self._get_route("GET", "/workflows/history")(request)

            self.assertIsInstance(workflows_response, list)
            self.assertEqual(create_response["name"], "workflow-api")
            self.assertEqual(run_response["status"], "success")
            self.assertIsInstance(workflow_history_response, list)
        finally:
            os.environ.pop("API_KEY", None)
            os.environ.pop("API_ROLE", None)

    def test_viewer_cannot_execute_tasks(self) -> None:
        os.environ["API_KEY"] = "secret"
        os.environ["API_ROLE"] = "viewer"
        try:
            request = type("Request", (), {"headers": {"x-api-key": "secret"}})()
            with self.assertRaises(Exception):
                self._get_route("POST", "/tasks/run")(type("Request", (), {"task_name": "hello"})(), request)
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
