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

## Scheduler

The project includes a simple scheduler module for one-time and recurring tasks. It integrates with the existing task registry, so any discovered task can be scheduled.

### CLI commands

Run a task immediately:

```bash
python -m zaya_ai_operations_agent.cli run --task hello
```

Schedule a one-time task:

```bash
python -m zaya_ai_operations_agent.cli schedule --task hello --once
```

Schedule a recurring task every 60 seconds:

```bash
python -m zaya_ai_operations_agent.cli schedule --task hello --interval 60
```

Schedule a recurring task every 2 minutes:

```bash
python -m zaya_ai_operations_agent.cli schedule --task hello --minutes 2
```

List scheduled tasks:

```bash
python -m zaya_ai_operations_agent.cli list-scheduled
```

## Agent Framework

The project includes a lightweight AI agent framework built on top of the task registry, scheduler, and memory store. The agent can:

- plan a task,
- execute a task,
- keep a history of previous executions,
- export execution logs to JSON.

### Agent CLI commands

Run an agent task:

```bash
python -m zaya_ai_operations_agent.cli agent run --task hello
```

Show execution history:

```bash
python -m zaya_ai_operations_agent.cli agent history
```

Export execution history to JSON:

```bash
python -m zaya_ai_operations_agent.cli agent export --output history.json
```

## API Server

The project also includes a FastAPI application for HTTP access to the agent.

### Endpoints

- GET /health - returns service health
- GET /tasks - lists available tasks
- POST /tasks/run - runs a task by name
- GET /history - returns agent execution history

### Run the API

```bash
uvicorn zaya_ai_operations_agent.api:app --reload
```

### API usage examples

Check health:

```bash
curl http://127.0.0.1:8000/health
```

List tasks:

```bash
curl http://127.0.0.1:8000/tasks
```

Run a task:

```bash
curl -X POST http://127.0.0.1:8000/tasks/run -H "Content-Type: application/json" -d '{"task_name":"hello"}'
```

View history:

```bash
curl http://127.0.0.1:8000/history
```

## Usage

Run the system-info task:

```bash
python -m zaya_ai_operations_agent.cli run --task system-info
```

Or via the installed script:

```bash
zaya-ai-operations-agent run --task hello
```
