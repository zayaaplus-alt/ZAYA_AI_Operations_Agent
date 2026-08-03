from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised when dependency is unavailable
    def load_dotenv(dotenv_path: Path | str, override: bool = False) -> bool:
        path = Path(dotenv_path)
        if not path.exists():
            return False

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if override or key not in os.environ:
                os.environ[key] = value

        return True


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment or defaults."""

    project_name: str = "zaya-ai-operations-agent"
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path("~/.zaya_ai_operations_agent").expanduser())
    memory_file: Optional[Path] = None
    openai_api_key: Optional[str] = None
    env_file: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.env_file is None:
            self.env_file = Path(".env")

        if self.env_file.exists():
            load_dotenv(self.env_file, override=False)

        env_values = os.environ.copy()

        if self.openai_api_key is None:
            self.openai_api_key = env_values.get("OPENAI_API_KEY") or None

        if self.log_level == "INFO" and env_values.get("LOG_LEVEL"):
            self.log_level = env_values.get("LOG_LEVEL", self.log_level)

        if self.memory_file is None:
            custom_memory = env_values.get("MEMORY_FILE")
            if custom_memory:
                self.memory_file = Path(custom_memory).expanduser()
            else:
                self.memory_file = self.data_dir / "memory.json"

        self.data_dir.mkdir(parents=True, exist_ok=True)
