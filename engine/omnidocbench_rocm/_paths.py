"""NFS-safe path resolution: heavy data lives on the big disk, never /workspace.

All large artifacts (datasets, eval venvs, predictions) derive from
:data_root`, which defaults to ``/root/ocr-eval/omnidocbench-rocm-data`` and
can be overridden via the ``OMNIDOCBENCH_ROCM_DATA`` env var. The repo checkout
under ``/workspace`` is a 10 GB NFS mount and must never receive heavy data.
"""
import os
from pathlib import Path


def data_root() -> Path:
    """Heavy data root on the big disk, never the 10 GB NFS repo."""
    return Path(os.environ.get("OMNIDOCBENCH_ROCM_DATA", "/root/ocr-eval/omnidocbench-rocm-data"))


def dataset_dir(version: str) -> Path:
    return data_root() / "datasets" / version


def eval_venv(platform: str) -> Path:
    return data_root() / "eval-venv" / platform


def predictions_dir(model_id: str, platform: str) -> Path:
    return data_root() / "predictions" / model_id / platform
