from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class Settings:
    """Application settings loaded from environment or defaults."""

    project_name: str = "zaya-ai-operations-agent"
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path("~/.zaya_ai_operations_agent").expanduser())
    memory_file: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.memory_file is None:
            self.memory_file = self.data_dir / "memory.json"

        self.data_dir.mkdir(parents=True, exist_ok=True)
