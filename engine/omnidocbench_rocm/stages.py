"""Four-stage orchestrator: download -> infer -> score -> publish.

Ports the gating + stage structure from
``AIwork4me/PaddleOCR-VL-ROCm/eval/run_eval.py``. The adapter is invoked as a
subprocess (filesystem-decoupled): the engine never imports it, only consumes
``out_dir/<image_stem>.md`` + ``_run_stats.json``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import importlib.util
from pathlib import Path

from . import artifact_utils as au
from .types import RunSummary, InferResult
from ._paths import dataset_dir, eval_venv, predictions_dir

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"}


def _build_adapter_command(*, adapter_path: Path, img_dir: Path, out_dir: Path,
                           platform: str, config: dict) -> list[str]:
    """Build the adapter subprocess argv. Forwards only truthy config keys.

    No shell=True, no string concatenation: every value is a separate argv
    element, so paths/URLs/model names with spaces are safe by construction.
    Unknown config keys are ignored.
    """
    cmd = [sys.executable, str(adapter_path),
           "--img-dir", str(img_dir), "--out-dir", str(out_dir),
           "--platform", platform]
    if config.get("backend"):
        cmd += ["--backend", str(config["backend"])]
    if config.get("server_url"):
        cmd += ["--server-url", str(config["server_url"])]
    if config.get("api_model_name"):
        cmd += ["--api-model-name", str(config["api_model_name"])]
    if config.get("skip_existing"):
        cmd += ["--skip-existing"]
    return cmd


def stage_download(version: str, revision: str | None = None) -> Path:
    """Pin revision; fetch OmniDocBench manifest + images to dataset_dir(version)."""
    from .download_omnidocbench import download_dataset
    if revision is None:
        raise SystemExit("OmniDocBench revision MUST be pinned for reproducibility (got None).")
    target = dataset_dir(version)
    resolved = download_dataset(repo_id="opendatalab/OmniDocBench", target=target, revision=revision)
    print(f"[download] OmniDocBench {version} ready: {resolved}")
    return target


def stage_infer(*, adapter_path: Path, img_dir: Path, out_dir: Path,
                platform: str, config: dict) -> InferResult:
    """Invoke the adapter as a SUBPROCESS (filesystem-decoupled). Never import it.

    Returns the loaded _run_stats.json plus the actual argv that ran (so the
    engine can record the real command in provenance).
    """
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_adapter_command(adapter_path=adapter_path, img_dir=img_dir,
                                 out_dir=out_dir, platform=platform, config=config)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"adapter failed (exit {proc.returncode}):\n{proc.stderr}")
    rs_path = out_dir / "_run_stats.json"
    if not rs_path.exists():
        raise SystemExit(f"adapter wrote no _run_stats.json: {rs_path}")
    run_stats = json.loads(rs_path.read_text(encoding="utf-8"))
    return InferResult(run_stats=run_stats, adapter_argv=cmd)


def _assert_full_set(run_stats_path: Path) -> dict:
    rs = json.loads(Path(run_stats_path).read_text(encoding="utf-8"))
    if rs.get("limit_pages") is not None:
        raise SystemExit(
            f"Refusing to publish official evidence from limited predictions "
            f"(limit_pages={rs['limit_pages']}). Run full unbounded inference first.")
    return rs


def stage_score(*, backend, predictions_dir: Path, version: str, cdm: bool,
                run_stats_path: Path, scoring_config: Path | None = None,
                dataset_dir: Path | None = None) -> Path:
    """Run pdf_validation.py inside the backend's eval-venv (3.11)."""
    return backend.score(predictions_dir=predictions_dir, version=version, cdm=cdm,
                         run_stats_path=run_stats_path, scoring_config=scoring_config,
                         dataset_dir=dataset_dir)


def stage_publish(*, model_id: str, platform: str, version: str, cdm: bool,
                  run_stats_path: Path, metric_result_path: Path, results_dir: Path,
                  git_commit: str, engine_version: str, adapter_command: str,
                  predictions_dir: Path, requested_backend: str = "",
                  server_url: str = "", api_model_name: str = "",
                  scoring_config_path: str = "", dataset_manifest_path: str = "",
                  dataset_revision: str = "", ground_truth_sha256: str = "",
                  prediction_source_commit: str = "", prediction_source_command: str = "",
                  prediction_source_run_manifest: str = "", migration_type: str = "") -> dict:
    """Publish a self-contained, committable evidence bundle into ``results_dir``.

    Copies the metric_result + run_stats (and, when supplied, the scoring
    config and dataset manifest) into the bundle so every artifact reference
    resolves within the repo. Emits a deterministic SHA256 prediction manifest
    and a dataset-identity artifact. Provenance distinguishes the packaging
    commit (this publish) from the prediction-source commit (the real
    inference), and records both committed-copy and redacted runtime paths.
    """
    run_stats = _assert_full_set(run_stats_path)
    actual_backend = run_stats.get("engine", "")
    if requested_backend and requested_backend != actual_backend:
        raise SystemExit(
            f"Refusing to publish: requested backend {requested_backend!r} "
            f"does not match adapter-reported engine {actual_backend!r}.")
    if scoring_config_path == "." or dataset_manifest_path == ".":
        raise SystemExit(
            "Refusing to publish: scoring_config_path/dataset_manifest_path must "
            "be real paths, not '.' (self-contained bundles require real inputs).")
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    save_name = f"{model_id}_{version}_quick_match{'_cdm' if cdm else ''}"

    # Required copies: metric + run_stats land in the bundle (clobber-safe by
    # CDM suffix in save_name).
    committed_metric = results_dir / f"{save_name}_metric_result.json"
    committed_stats = results_dir / f"{save_name}_run_stats.json"
    au.copy_artifact(source=Path(metric_result_path), destination=committed_metric)
    au.copy_artifact(source=Path(run_stats_path), destination=committed_stats)

    # Optional: rendered scoring config (real path only).
    committed_scoring = None
    if scoring_config_path:
        committed_scoring = results_dir / f"{save_name}_scoring_config.yaml"
        au.copy_artifact(source=Path(scoring_config_path), destination=committed_scoring)

    # Dataset identity: copy a real manifest, else synthesize a minimal identity.
    if dataset_manifest_path and Path(dataset_manifest_path).is_file():
        committed_dataset = results_dir / f"{save_name}_dataset_manifest.json"
        au.copy_artifact(source=Path(dataset_manifest_path), destination=committed_dataset)
    else:
        committed_dataset = results_dir / f"{save_name}_dataset_identity.json"
        au.write_dataset_identity(
            destination=committed_dataset, dataset="OmniDocBench", version=version,
            revision=dataset_revision, ground_truth_file="OmniDocBench.json",
            ground_truth_sha256=ground_truth_sha256)

    # Prediction manifest (deterministic SHA256 over non-empty .md).
    committed_manifest = results_dir / f"{save_name}_prediction_manifest.json"
    au.write_prediction_manifest(
        predictions_dir=Path(predictions_dir), destination=committed_manifest,
        model_id=model_id, platform=platform, backend=actual_backend, run_stats=run_stats)
    manifest_sha = hashlib.sha256(committed_manifest.read_bytes()).hexdigest()

    summary_path = results_dir / f"{save_name}_run_summary.json"
    provenance_path = results_dir / f"{save_name}_provenance.json"
    au.write_run_summary(
        save_name=save_name, run_stats_path=Path(run_stats_path),
        metric_result_path=Path(metric_result_path),
        committed_metric_result_path=committed_metric,
        committed_run_stats_path=committed_stats, destination=summary_path, cdm=cdm)
    au.write_provenance(
        destination=provenance_path, git_commit=git_commit, engine_version=engine_version,
        model_id=model_id, platform=platform, server_url=server_url,
        api_model_name=api_model_name, adapter_command=adapter_command,
        scoring_config_path=Path(scoring_config_path),
        dataset_manifest_path=Path(dataset_manifest_path),
        dataset_identity_path=committed_dataset, dataset_revision=dataset_revision,
        predictions_dir=Path(predictions_dir),
        prediction_manifest_path=committed_manifest, prediction_manifest_sha256=manifest_sha,
        metric_result_paths=[committed_metric], run_summary_paths=[summary_path],
        run_stats_path=committed_stats,
        source_metric_result_path=str(metric_result_path),
        source_run_stats_path=str(run_stats_path),
        source_prediction_dir=str(predictions_dir),
        packaging_commit=git_commit, prediction_source_commit=prediction_source_commit,
        prediction_source_command=prediction_source_command,
        prediction_source_run_manifest=prediction_source_run_manifest,
        migration_type=migration_type)
    return {
        "run_summary": str(summary_path), "provenance": str(provenance_path),
        "metric_result": str(committed_metric), "run_stats": str(committed_stats),
        "prediction_manifest": str(committed_manifest),
        "dataset_identity": str(committed_dataset),
        "scoring_config": str(committed_scoring) if committed_scoring else None,
    }
