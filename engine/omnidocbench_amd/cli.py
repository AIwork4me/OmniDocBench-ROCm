"""Argparse CLI wiring ``cdm``/``dataset``/``infer``/``score``/``publish``/``run``
subcommands to :mod:`omnidocbench_amd.stages` + :mod:`backends`.

Registered as the ``omnidocbench-amd`` console script
(``omnidocbench-amd = "omnidocbench_amd.cli:main"`` in ``pyproject.toml``).

The ``run`` subcommand is a Task 13 placeholder: it raises ``SystemExit`` until
the orchestrator (all stages + backend) is wired.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import omnidocbench_amd
from .stages import stage_download, stage_infer, stage_publish, stage_score
from .backends import get_backend


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="omnidocbench-amd")
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
    rn.add_argument("--stage", default="all")
    rn.add_argument("--platform", required=True)

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
            engine_version=omnidocbench_amd.__version__,
            adapter_command=a.adapter_command, server_url=a.server_url,
            api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
            dataset_manifest_path=a.dataset_manifest, dataset_revision=a.dataset_revision)
        return 0
    if a.cmd == "run":
        raise SystemExit("orchestrated 'run' is wired in Task 13 (needs all stages + backend)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
