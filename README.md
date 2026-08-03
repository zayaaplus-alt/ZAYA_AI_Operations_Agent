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

## Multi-Agent Orchestration

The project now includes a modular multi-agent orchestration layer with three specialist agents:

- PlannerAgent: creates an execution plan from a task name
- ExecutorAgent: runs the task through the existing task registry
- ReviewerAgent: validates the result before the run is marked successful

The AgentManager coordinates them and records every execution in the shared history store.

### Agent API endpoints

List available agents:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/agents
```

Run a multi-agent workflow:

```bash
curl -X POST http://127.0.0.1:8000/agents/run -H "Content-Type: application/json" -H "x-api-key: your-secret-key" -d '{"task_name":"hello","user_role":"admin"}'
```

## Workflow Engine

The project now includes a modular workflow engine for composing multiple tasks into a single execution flow.

Each workflow supports:

- workflow name
- ordered task list
- conditional execution via `always`, `success`, or `failure`
- retry policy with configurable max retries and retry delay

### Example workflow

```json
{
  "name": "ops-workflow",
  "steps": [
    {"task_name": "hello", "condition": "always"},
    {"task_name": "system-info", "condition": "success"}
  ],
  "retry_policy": {
    "max_retries": 1,
    "retry_delay_seconds": 0
  }
}
```

### Workflow API examples

Create a workflow:

```bash
curl -X POST http://127.0.0.1:8000/workflows -H "Content-Type: application/json" -H "x-api-key: your-secret-key" -d '{"name":"ops-workflow","steps":[{"task_name":"hello","condition":"always"}],"retry_policy":{"max_retries":1}}'
```

List workflows:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/workflows
```

Run a workflow:

```bash
curl -X POST http://127.0.0.1:8000/workflows/run -H "Content-Type: application/json" -H "x-api-key: your-secret-key" -d '{"workflow_name":"ops-workflow","user_role":"operator"}'
```

Inspect workflow execution history:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/workflows/history
```

## Knowledge Base and Memory

The project now includes a modular knowledge base layer for ingesting and searching documents.

### Capabilities

- document ingestion from Markdown, TXT, and PDF-like text files
- document metadata and timestamps
- chunking for long content
- vector storage abstraction with a pluggable embedding interface
- semantic-style search over indexed chunks

### Example knowledge upload

```bash
curl -X POST http://127.0.0.1:8000/knowledge/upload -H "Content-Type: application/json" -H "x-api-key: your-secret-key" -d '{"path":"/path/to/notes.md","title":"Notes","metadata":{"source":"internal"}}'
```

### Search and document listing

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/knowledge/search?query=example
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/knowledge/documents
```

### Delete a document

```bash
curl -X DELETE http://127.0.0.1:8000/knowledge/document/<document-id> -H "x-api-key: your-secret-key"
```

## Dashboard

The API serves a lightweight HTML dashboard at / and /dashboard. It shows:

- system status,
- registered tasks,
- scheduled tasks,
- recent execution history.

The page auto-refreshes every 10 seconds. The dashboard is available without authentication, while the protected API endpoints still require an API key and role.

Open the dashboard in a browser:

```bash
http://127.0.0.1:8000/
```

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

Set the following values in your .env file before using the API:

```bash
API_KEY=your-secret-key
API_ROLE=admin
```

Check health:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/health
```

List tasks:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/tasks
```

Run a task:

```bash
curl -X POST http://127.0.0.1:8000/tasks/run -H "Content-Type: application/json" -H "x-api-key: your-secret-key" -d '{"task_name":"hello"}'
```

View history:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/history
```

View history for one task:

```bash
curl -H "x-api-key: your-secret-key" http://127.0.0.1:8000/history/hello
```

Delete history (admin only):

```bash
curl -X DELETE -H "x-api-key: your-secret-key" http://127.0.0.1:8000/history
```

### Roles

- admin: can access all endpoints
- operator: can access all endpoints except some administrative actions if added later
- viewer: can access read-only endpoints such as /health, /tasks, and /history

## Usage

Run the system-info task:

```bash
python -m zaya_ai_operations_agent.cli run --task system-info
```

Or via the installed script:

```bash
zaya-ai-operations-agent run --task hello
```
