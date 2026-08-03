from __future__ import annotations

import html
from pathlib import Path
from typing import Any


def build_dashboard_html(data: dict[str, Any]) -> str:
    tasks = "".join(
        f"<li>{html.escape(task['name'])}: {html.escape(task.get('description', ''))}</li>"
        for task in data.get("tasks", [])
    )
    scheduled = "".join(
        f"<li>{html.escape(item['task_name'])} (next run: {html.escape(item['next_run_at'])})</li>"
        for item in data.get("scheduled_tasks", [])
    )
    history = "".join(
        f"<li>{html.escape(item['executed_at'])} - {html.escape(item['task_name'])} - {html.escape(item['status'])}</li>"
        for item in data.get("history", [])
    )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta http-equiv=\"refresh\" content=\"10\" />
  <title>ZAYA AI Operations Agent Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    section {{ margin-bottom: 2rem; }}
    code {{ background: #f3f3f3; padding: 0.1rem 0.3rem; }}
  </style>
</head>
<body>
  <h1>ZAYA AI Operations Agent Dashboard</h1>
  <p>Status: <strong>{html.escape(data.get('status', 'unknown'))}</strong></p>

  <section>
    <h2>System Status</h2>
    <ul>
      <li>Project: {html.escape(data.get('project_name', ''))}</li>
      <li>Log level: {html.escape(data.get('log_level', ''))}</li>
      <li>Memory file: {html.escape(data.get('memory_file', ''))}</li>
    </ul>
  </section>

  <section>
    <h2>Registered Tasks</h2>
    <ul>{tasks or '<li>No tasks registered</li>'}</ul>
  </section>

  <section>
    <h2>Scheduled Tasks</h2>
    <ul>{scheduled or '<li>No scheduled tasks</li>'}</ul>
  </section>

  <section>
    <h2>Recent Execution History</h2>
    <ul>{history or '<li>No history available</li>'}</ul>
  </section>
</body>
</html>
"""
