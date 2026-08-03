# ZAYA AI Operations Agent

A clean, modular Python scaffold for an AI Operations Agent with separate modules for configuration, logging, tasks, memory, and CLI.

## Structure

- src/zaya_ai_operations_agent/config.py - typed settings and configuration defaults
- src/zaya_ai_operations_agent/logging_utils.py - logger setup
- src/zaya_ai_operations_agent/tasks.py - task definitions and handlers
- src/zaya_ai_operations_agent/memory.py - JSON-backed memory store
- src/zaya_ai_operations_agent/cli.py - CLI entry point and parser

## Configuration

The project loads configuration from a dotenv file named .env if present. A sample file is included at [.env.example](.env.example).

Supported variables:

- OPENAI_API_KEY: API key for OpenAI-backed integrations
- LOG_LEVEL: logging verbosity such as INFO, DEBUG, WARNING
- MEMORY_FILE: optional path for the JSON memory store

Example:

```bash
cp .env.example .env
```

## Task System

Tasks are registered through a lightweight plugin model. New tasks can be added by creating a new module in the tasks_plugins package and exposing a registration function. The CLI discovers tasks from that package automatically, so no changes to cli.py are required.

Built-in example tasks:

- hello: prints a friendly greeting
- system-info: prints basic system information

## Usage

Run the hello task:

```bash
python -m zaya_ai_operations_agent.cli run --task hello
```

Run the system-info task:

```bash
python -m zaya_ai_operations_agent.cli run --task system-info
```

Or via the installed script:

```bash
zaya-ai-operations-agent run --task hello
```
