from __future__ import annotations

import platform
import socket

from ..tasks import Task


def register_system_info_task(registry: dict[str, Task]) -> None:
    def handler() -> None:
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "hostname": socket.gethostname(),
        }
        print("System Information")
        for key, value in info.items():
            print(f"{key}: {value}")

    registry["system-info"] = Task(
        name="system-info",
        description="Print basic system information",
        handler=handler,
    )
