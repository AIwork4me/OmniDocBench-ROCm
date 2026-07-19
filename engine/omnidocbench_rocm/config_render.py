"""Render an OmniDocBench scoring config from a template.

OmniDocBench scoring is config-driven: ``pdf_validation.py --config <yaml>``.
Predictions + ground truth live *inside* the config, not as CLI flags. CDM is
enabled by adding ``CDM`` to ``display_formula.metric`` (+ ``cdm_workers``).
"""
from __future__ import annotations
import os
import tempfile
import yaml
from pathlib import Path


def render_config(template_path: Path, *, prediction_path: Path,
                  gt_path: Path, cdm: bool, workers: int = 13) -> Path:
    """Render the template into a concrete config YAML and return its path.

    Overwrites ``dataset.prediction.data_path`` + ``dataset.ground_truth.data_path``.
    When ``cdm`` is True, appends ``CDM`` to ``display_formula.metric`` and sets
    ``cdm_workers`` (matches the ``unlimited_rocm_30_cdm.yaml`` precedent).
    Writes to a tempfile so the package data dir is not polluted; pdf_validation
    reads it by absolute path.
    """
    template_path = Path(template_path)
    cfg = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    ds = cfg["end2end_eval"]["dataset"]
    ds["prediction"]["data_path"] = str(prediction_path)
    ds["ground_truth"]["data_path"] = str(gt_path)
    if cdm:
        df = cfg["end2end_eval"]["metrics"]["display_formula"]
        metric = df.setdefault("metric", [])
        if "CDM" not in metric:
            metric.append("CDM")
        df.setdefault("cdm_workers", workers)
    fd, name = tempfile.mkstemp(prefix="omnidocbench_cfg_", suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(yaml.safe_dump(cfg, sort_keys=False))
    return Path(name)
