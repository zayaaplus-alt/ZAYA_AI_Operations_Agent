import importlib
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from zaya_ai_operations_agent.cli import build_parser, run_task
from zaya_ai_operations_agent.config import Settings
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


if __name__ == "__main__":
    unittest.main()
