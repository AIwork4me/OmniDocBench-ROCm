from __future__ import annotations
from pathlib import Path
from .base import Backend
from .linux_rocm import LinuxRocmBackend

__all__ = ["Backend", "LinuxRocmBackend", "get_backend"]

_WINDOWS_HIP_NOT_IMPLEMENTED = (
    "The 'windows-hip' backend is planned/onboarding and not yet implemented. "
    "Linux-ROCm is the only implemented backend today; see "
    "contracts/backend-policy.md for the platform roadmap."
)


def get_backend(platform: str, checkout: Path | None = None) -> Backend:
    """Return the platform backend.

    Only ``linux-rocm`` is implemented today. ``windows-hip`` is planned
    (onboarding) and raises a clear, honest error rather than pretending a
    backend exists. See ``contracts/backend-policy.md``.
    """
    if platform == "linux-rocm":
        return LinuxRocmBackend(checkout=checkout)
    if platform == "windows-hip":
        raise NotImplementedError(_WINDOWS_HIP_NOT_IMPLEMENTED)
    raise ValueError(f"unknown platform: {platform}")
