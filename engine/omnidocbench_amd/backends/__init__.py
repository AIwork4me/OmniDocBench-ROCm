from __future__ import annotations
from pathlib import Path
from .base import Backend
from .linux_rocm import LinuxRocmBackend

__all__ = ["Backend", "LinuxRocmBackend", "get_backend"]


def get_backend(platform: str, checkout: Path | None = None) -> Backend:
    """Return the platform backend.

    ``windows-hip`` is lazy-imported so the engine works without the Windows
    backend (Task 15) installed.
    """
    if platform == "linux-rocm":
        return LinuxRocmBackend(checkout=checkout)
    if platform == "windows-hip":
        from .windows_hip import WindowsHipBackend
        return WindowsHipBackend(checkout=checkout)
    raise ValueError(f"unknown platform: {platform}")
