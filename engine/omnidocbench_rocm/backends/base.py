from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path


class Backend(ABC):
    """Platform-specific scoring + CDM provisioning."""

    @abstractmethod
    def ensure_checkout(self, revision: str) -> Path: ...

    @abstractmethod
    def provision_cdm(self) -> None: ...

    @abstractmethod
    def score(self, *, predictions_dir: Path, version: str, cdm: bool,
              run_stats_path: Path, scoring_config: Path | None = None,
              dataset_dir: Path | None = None) -> Path:
        """Run pdf_validation.py in the eval-venv (3.11). Return metric_result path."""
