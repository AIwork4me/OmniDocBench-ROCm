"""Argparse CLI wiring ``cdm``/``dataset``/``infer``/``score``/``publish``/``run``
subcommands to :mod:`omnidocbench_rocm.stages` + :mod:`backends`.

Registered as the ``omnidocbench-rocm`` console script
(``omnidocbench-rocm = "omnidocbench_rocm.cli:main"`` in ``pyproject.toml``).

The ``run`` subcommand orchestrates the full four-stage pipeline
(``download -> infer -> score -> publish``) when invoked with
``--stage all``; single stages (``download``/``infer``/``score``/``publish``)
dispatch to just that stage.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import omnidocbench_rocm
from .stages import stage_download, stage_infer, stage_publish, stage_score
from .backends import get_backend
from .conformance import check_repo
from ._paths import dataset_dir, predictions_dir


def _orchestrate_run(a) -> int:
    """Run the four-stage pipeline (``download -> infer -> score -> publish``).

    For ``--stage all`` the stages execute in order, threading artifacts:
    ``stage_download`` returns the dataset dir; ``stage_infer`` writes
    predictions + ``_run_stats.json`` and returns the run-stats dict;
    ``stage_score`` consumes the run-stats path and writes the metric result;
    ``stage_publish`` assembles the run_summary + provenance artifacts.

    Single-stage values (``download``/``infer``/``score``/``publish``) dispatch
    to just that stage with the same argument plumbing.
    """
    stage = a.stage
    img_dir = dataset_dir(a.version) / "images"
    out_dir = predictions_dir(a.model_id, a.platform)
    run_stats_path = out_dir / "_run_stats.json"

    if stage == "download":
        stage_download(a.version, a.revision)
        return 0

    if stage == "infer":
        stage_infer(adapter_path=Path(a.adapter), img_dir=img_dir,
                    out_dir=out_dir, platform=a.platform, config={})
        return 0

    if stage == "score":
        backend = get_backend(a.platform)
        stage_score(backend=backend, predictions_dir=out_dir,
                    version=a.version, cdm=a.cdm,
                    run_stats_path=run_stats_path)
        return 0

    if stage == "publish":
        metric_path = out_dir.parent / "metric_result.json"
        stage_publish(
            model_id=a.model_id, platform=a.platform, version=a.version,
            cdm=a.cdm, run_stats_path=run_stats_path,
            metric_result_path=metric_path, results_dir=Path(a.results_dir),
            git_commit=a.git_commit, engine_version=omnidocbench_rocm.__version__,
            adapter_command=a.adapter_command, server_url=a.server_url,
            api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
            dataset_manifest_path=a.dataset_manifest, dataset_revision=a.revision)
        return 0

    # stage == "all": full pipeline in order.
    stage_download(a.version, a.revision)
    # stage_infer writes _run_stats.json into out_dir and returns the dict;
    # score/publish consume the path (exact bytes the adapter produced).
    _run_stats = stage_infer(adapter_path=Path(a.adapter), img_dir=img_dir,
                             out_dir=out_dir, platform=a.platform, config={})
    backend = get_backend(a.platform)
    metric_result_path = stage_score(
        backend=backend, predictions_dir=out_dir, version=a.version,
        cdm=a.cdm, run_stats_path=run_stats_path)
    stage_publish(
        model_id=a.model_id, platform=a.platform, version=a.version,
        cdm=a.cdm, run_stats_path=run_stats_path,
        metric_result_path=metric_result_path, results_dir=Path(a.results_dir),
        git_commit=a.git_commit, engine_version=omnidocbench_rocm.__version__,
        adapter_command=a.adapter_command, server_url=a.server_url,
        api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
        dataset_manifest_path=a.dataset_manifest, dataset_revision=a.revision)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="omnidocbench-rocm")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("cdm")
    sp.add_argument("setup")
    sp.add_argument("--platform", required=True)

    dp = sub.add_parser("dataset")
    dp.add_argument("download")
    dp.add_argument("--version", default="v16")
    dp.add_argument("--revision", required=True)

    ip = sub.add_parser("infer")
    ip.add_argument("--adapter", required=True)
    ip.add_argument("--img-dir", required=True)
    ip.add_argument("--out-dir", required=True)
    ip.add_argument("--platform", required=True)

    sc = sub.add_parser("score")
    sc.add_argument("--platform", required=True)
    sc.add_argument("--predictions-dir", required=True)
    sc.add_argument("--version", default="v16")
    sc.add_argument("--cdm", action="store_true")
    sc.add_argument("--run-stats", required=True)

    pu = sub.add_parser("publish")
    pu.add_argument("--model-id", required=True)
    pu.add_argument("--platform", required=True)
    pu.add_argument("--version", default="v16")
    pu.add_argument("--cdm", action="store_true")
    pu.add_argument("--run-stats", required=True)
    pu.add_argument("--metric-result", required=True)
    pu.add_argument("--results-dir", required=True)
    pu.add_argument("--git-commit", required=True)
    pu.add_argument("--adapter-command", required=True)
    pu.add_argument("--server-url", default="")
    pu.add_argument("--api-model-name", default="")
    pu.add_argument("--scoring-config", default="")
    pu.add_argument("--dataset-manifest", default="")
    pu.add_argument("--dataset-revision", required=True)

    rn = sub.add_parser("run")
    rn.add_argument("--stage", default="all",
                    choices=["all", "download", "infer", "score", "publish"])
    rn.add_argument("--platform", required=True)
    rn.add_argument("--version", default="v16")
    rn.add_argument("--revision", required=True)
    rn.add_argument("--adapter", required=True,
                    help="path to run_adapter.py (invoked as a subprocess)")
    rn.add_argument("--model-id", required=True)
    rn.add_argument("--git-commit", required=True, help="provenance: repo HEAD")
    rn.add_argument("--results-dir", required=True,
                    help="where run_summary/provenance artifacts are written")
    rn.add_argument("--cdm", action="store_true",
                    help="score with the CDM (document markup) variant")
    rn.add_argument("--adapter-command", default="",
                    help="provenance: command that launched the adapter")
    rn.add_argument("--server-url", default="")
    rn.add_argument("--api-model-name", default="")
    rn.add_argument("--scoring-config", default="")
    rn.add_argument("--dataset-manifest", default="")

    cf = sub.add_parser("conformance")
    cf.add_argument("repo_path")

    a = p.parse_args(argv)

    if a.cmd == "cdm":
        get_backend(a.platform).provision_cdm()
        return 0
    if a.cmd == "dataset":
        stage_download(a.version, a.revision)
        return 0
    if a.cmd == "infer":
        stage_infer(adapter_path=Path(a.adapter), img_dir=Path(a.img_dir),
                    out_dir=Path(a.out_dir), platform=a.platform, config={})
        return 0
    if a.cmd == "score":
        b = get_backend(a.platform)
        stage_score(backend=b, predictions_dir=Path(a.predictions_dir),
                    version=a.version, cdm=a.cdm,
                    run_stats_path=Path(a.run_stats))
        return 0
    if a.cmd == "publish":
        stage_publish(
            model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
            run_stats_path=Path(a.run_stats), metric_result_path=Path(a.metric_result),
            results_dir=Path(a.results_dir), git_commit=a.git_commit,
            engine_version=omnidocbench_rocm.__version__,
            adapter_command=a.adapter_command, server_url=a.server_url,
            api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
            dataset_manifest_path=a.dataset_manifest, dataset_revision=a.dataset_revision)
        return 0
    if a.cmd == "run":
        return _orchestrate_run(a)
    if a.cmd == "conformance":
        report = check_repo(Path(a.repo_path))
        if report.ok:
            print("CONFORMANT"); return 0
        print("NON-CONFORMANT:")
        for f in report.failures:
            print(" -", f)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
