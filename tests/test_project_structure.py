import importlib
import unittest


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
        from zaya_ai_operations_agent.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["run", "--task", "hello"])

        self.assertEqual(args.command, "run")
        self.assertEqual(args.task, "hello")


if __name__ == "__main__":
    unittest.main()
