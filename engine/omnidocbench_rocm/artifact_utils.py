"""Artifact-assembly utilities: run summaries, provenance, model cards.

Ported + standardized from AIwork4me/PaddleOCR-VL-ROCm/eval/artifact_utils.py
to schema v1 (contracts/artifact-schema.json). Every emitted object carries
``schema_version: 1`` and is validated via :func:`validate_artifact` before
being written to disk.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schema import validate_artifact

OFFICIAL_LOCAL_STEM = "paddleocr_official_local_llamacpp_gguf"


@dataclass(frozen=True)
class ArtifactPaths:
    predictions_dir: Path
    metric_result: Path
    run_summary: Path
    provenance: Path


def official_local_paths(version: str, *, cdm: bool = False) -> ArtifactPaths:
    results_dir = Path("results/omnidocbench") / version
    suffix = "_cdm" if cdm else ""
    return ArtifactPaths(
        predictions_dir=Path("predictions") / f"{OFFICIAL_LOCAL_STEM}_{version}",
        metric_result=results_dir / f"{OFFICIAL_LOCAL_STEM}_quick_match_metric_result{suffix}.json",
        run_summary=results_dir / f"{OFFICIAL_LOCAL_STEM}_quick_match_run_summary{suffix}.json",
        provenance=results_dir / f"{OFFICIAL_LOCAL_STEM}_provenance.json",
    )


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_metric_report(source: Path, destination: Path) -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"Metric report not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def copy_artifact(*, source: Path, destination: Path) -> Path:
    """Copy a required artifact into the results bundle.

    Fails loudly when the source is absent (never silently skip a missing
    metric/run_stats). Creates parent dirs; uses ``shutil.copyfile``.
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Artifact source not found: {source}")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def write_prediction_manifest(*, predictions_dir: Path, destination: Path,
                              model_id: str, platform: str, backend: str,
                              run_stats: dict) -> Path:
    """Deterministic SHA256 manifest of the run's non-empty ``.md`` predictions.

    Run-driven: iterates ``run_stats["stats"]`` (the pages the run actually
    scored) and records the non-empty Markdown for each, so the manifest
    describes THIS run — not stray files a dirty predictions directory may
    contain. ``failed_pages`` records run pages whose prediction is missing or
    empty. Falls back to globbing all non-empty ``*.md`` only when the run
    carries no ``stats`` (degenerate/test case). ``source_prediction_dir`` is
    the runtime path (redacted downstream). Output is deterministic (sorted
    keys + sorted lists).
    """
    predictions_dir = Path(predictions_dir)
    stats = run_stats.get("stats") or []
    files: list[dict] = []
    failed: list[dict] = []
    if stats:
        seen: set[str] = set()
        for item in stats:
            if not isinstance(item, dict):
                continue
            image = item.get("image", "")
            if not image:
                continue
            md_name = Path(image).stem + ".md"
            if md_name in seen:
                continue
            seen.add(md_name)
            status = str(item.get("status", ""))
            md_path = predictions_dir / md_name
            if md_path.is_file() and md_path.stat().st_size > 0:
                files.append({"relative_path": md_name,
                              "sha256": hashlib.sha256(md_path.read_bytes()).hexdigest(),
                              "size_bytes": md_path.stat().st_size})
            else:
                reason = str(item.get("error", status)) or "missing/empty prediction"
                failed.append({"relative_path": md_name, "reason": reason})
    else:
        # Degenerate fallback: no per-page stats → record every non-empty .md.
        for path in sorted(predictions_dir.glob("*.md")):
            if path.stat().st_size == 0:
                continue
            files.append({"relative_path": path.name,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                          "size_bytes": path.stat().st_size})
    files.sort(key=lambda f: f["relative_path"])
    failed.sort(key=lambda f: f["relative_path"])
    manifest = {
        "schema_version": 1,
        "model_id": model_id,
        "platform": platform,
        "backend": backend,
        "prediction_count": len(files),
        "expected_page_count": run_stats.get("count"),
        "failed_page_count": run_stats.get("fail"),
        "source_prediction_dir": str(predictions_dir),
        "hash_algorithm": "sha256",
        "files": files,
        "failed_pages": failed,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    return destination


def write_dataset_identity(*, destination: Path, dataset: str, version: str,
                           revision: str, ground_truth_file: str,
                           ground_truth_sha256: str) -> Path:
    """Minimal dataset identity artifact when no full manifest is available.

    Records the dataset name/version, pinned revision, the GT JSON filename,
    and its SHA256 (so the bundle is self-identifying without a private path).
    """
    ident = {"schema_version": 1, "dataset": dataset, "version": version,
             "revision": revision, "ground_truth_file": ground_truth_file,
             "ground_truth_sha256": ground_truth_sha256 or "not_recorded"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(ident, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    return destination


def _nested(metric: dict[str, Any], *keys: str) -> Any:
    value: Any = metric
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _nested_number(metric: dict[str, Any], *keys: str) -> float | None:
    value = _nested(metric, *keys)
    return value if isinstance(value, (int, float)) else None


def analyze_metric_quality(metric: dict[str, Any]) -> dict[str, Any]:
    cdm_debug = _nested(metric, "display_formula", "metric_debug", "CDM") or {}
    sample_count = cdm_debug.get("sample_count") if isinstance(cdm_debug, dict) else None
    exception_count = cdm_debug.get("exception_case_count") if isinstance(cdm_debug, dict) else None
    formula_cdm = {
        "valid": True,
        "reason": "",
        "sample_count": sample_count,
        "exception_case_count": exception_count,
    }
    if (
        isinstance(sample_count, int)
        and sample_count > 0
        and isinstance(exception_count, int)
        and exception_count >= sample_count
    ):
        first_reason = ""
        exception_cases = cdm_debug.get("exception_cases", [])
        if exception_cases and isinstance(exception_cases[0], dict):
            first_reason = str(exception_cases[0].get("reason", ""))
        formula_cdm["valid"] = False
        formula_cdm["reason"] = (
            f"all CDM samples raised exceptions ({exception_count}/{sample_count}); "
            f"first_reason={first_reason}"
        )
    return {"formula_cdm": formula_cdm}


def extract_readme_metrics(metric: dict[str, Any]) -> dict[str, float | None]:
    quality = analyze_metric_quality(metric)
    cdm_value = _nested_number(metric, "display_formula", "page", "CDM", "ALL")
    if not quality["formula_cdm"]["valid"]:
        cdm_value = None

    return {
        "text_edit_dist": _nested_number(metric, "text_block", "page", "Edit_dist", "ALL"),
        "reading_order_edit_dist": _nested_number(
            metric, "reading_order", "page", "Edit_dist", "ALL"
        ),
        "table_teds_percent": (
            _nested_number(metric, "table", "page", "TEDS", "ALL") * 100
            if _nested_number(metric, "table", "page", "TEDS", "ALL") is not None
            else None
        ),
        "formula_cdm_percent": cdm_value * 100 if cdm_value is not None else None,
    }


def write_run_summary(
    *,
    save_name: str,
    run_stats_path: Path,
    metric_result_path: Path,
    destination: Path,
    cdm: bool,
    committed_metric_result_path: Path | None = None,
    committed_run_stats_path: Path | None = None,
) -> Path:
    run_stats = load_json(run_stats_path)
    metric_result = load_json(metric_result_path)
    failures = [
        {
            key: (value[:200] if isinstance(value, str) else value)
            for key, value in item.items()
            if key in {"image", "status", "error", "seconds", "attempts"}
        }
        for item in run_stats.get("stats", [])
        if isinstance(item, dict) and str(item.get("status", "")).startswith(("fail", "fallback"))
    ][:20]
    run_stats_summary = {
        "count": run_stats.get("count"),
        "ok": run_stats.get("ok"),
        "fail": run_stats.get("fail"),
        "fallback": run_stats.get("fallback"),
        "limit_pages": run_stats.get("limit_pages"),
        "failure_samples": failures,
    }
    # Self-contained bundles record the committed (repo-relative) copy path;
    # fall back to the runtime source for callers that did not stage copies.
    recorded_metric = committed_metric_result_path or metric_result_path
    recorded_stats = committed_run_stats_path or run_stats_path
    summary = {
        "schema_version": 1,
        "save_name": save_name,
        "engine": run_stats.get("engine"),
        "cdm": cdm,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "prediction_count": run_stats.get("count"),
        "ok_pages": run_stats.get("ok"),
        "failed_pages": run_stats.get("fail"),
        "fallback_pages": run_stats.get("fallback"),
        "metric_result_path": str(recorded_metric),
        "run_stats_path": str(recorded_stats),
        "readme_metrics": extract_readme_metrics(metric_result),
        "metric_quality": analyze_metric_quality(metric_result),
        "run_stats_summary": run_stats_summary,
    }
    validate_artifact("run_summary", summary)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def write_provenance(
    *,
    destination: Path,
    git_commit: str,
    engine_version: str,
    model_id: str,
    platform: str,
    server_url: str,
    api_model_name: str,
    adapter_command: str,
    scoring_config_path: Path,
    dataset_manifest_path: Path,
    dataset_revision: str,
    predictions_dir: Path,
    metric_result_paths: list[Path],
    run_summary_paths: list[Path],
    run_stats_path: Path,
    dataset_identity_path: Path | None = None,
    prediction_manifest_path: Path | None = None,
    prediction_manifest_sha256: str = "",
    source_metric_result_path: str = "",
    source_run_stats_path: str = "",
    source_prediction_dir: str = "",
    packaging_commit: str = "",
    prediction_source_commit: str = "",
    prediction_source_command: str = "",
    prediction_source_run_manifest: str = "",
    migration_type: str = "",
) -> Path:
    run_stats = load_json(run_stats_path)
    provenance = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "engine_version": engine_version,
        "model_id": model_id,
        "platform": platform,
        "vlm_server_url": server_url,
        "api_model_name": api_model_name,
        "adapter_command": adapter_command,
        "scoring_config_path": str(scoring_config_path),
        "dataset_manifest_path": str(dataset_manifest_path),
        "dataset_revision": dataset_revision,
        "prediction_dir": str(predictions_dir),
        "page_count": run_stats.get("count"),
        "ok_pages": run_stats.get("ok"),
        "failed_pages": run_stats.get("fail"),
        "fallback_pages": run_stats.get("fallback"),
        "metric_result_paths": [str(path) for path in metric_result_paths],
        "run_summary_paths": [str(path) for path in run_summary_paths],
        "run_stats_path": str(run_stats_path),
        "backend": run_stats.get("engine", ""),   # adapter-reported (_run_stats.json)
        # Self-contained-bundle + migration provenance (all optional).
        "packaging_commit": packaging_commit or git_commit,
        "prediction_source_commit": prediction_source_commit,
        "prediction_source_command": prediction_source_command,
        "prediction_source_run_manifest": prediction_source_run_manifest,
        "prediction_manifest_path": str(prediction_manifest_path) if prediction_manifest_path else "",
        "prediction_manifest_sha256": prediction_manifest_sha256,
        "dataset_identity_path": str(dataset_identity_path) if dataset_identity_path else "",
        "source_metric_result_path": source_metric_result_path,
        "source_run_stats_path": source_run_stats_path,
        "source_prediction_dir": source_prediction_dir,
        "migration_type": migration_type,
    }
    validate_artifact("provenance", provenance)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def write_model_card(
    *,
    destination: Path,
    model_id: str,
    model_version: str,
    platforms: list[str],
    badge: dict[str, str],
    omnidocbench_version: str,
    overall: float | None,
    submetrics: dict[str, Any],
    hardware: dict[str, Any],
    artifacts: dict[str, Any],
    eval_date: str,
) -> Path:
    card = {
        "schema_version": 1,
        "model_id": model_id,
        "model_version": model_version,
        "platforms": platforms,
        "badge": badge,
        "eval_date": eval_date,
        "omnidocbench_version": omnidocbench_version,
        "overall": overall,
        "submetrics": submetrics,
        "hardware": hardware,
        "artifacts": artifacts,
    }
    validate_artifact("model_card", card)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination
