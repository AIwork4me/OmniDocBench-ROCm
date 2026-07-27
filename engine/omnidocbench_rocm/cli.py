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
import shlex
import sys
from pathlib import Path

import omnidocbench_rocm
from .stages import stage_download, stage_infer, stage_publish, stage_score
from .backends import get_backend
from .conformance import check_repo
from .bundle_validator import validate_bundle
from ._paths import dataset_dir, predictions_dir


def _infer_config_from_args(a) -> dict:
    """One source of truth for the adapter config dict. Shared by `infer` and `run`.

    Empty strings / False are omitted downstream by _build_adapter_command.
    """
    return {"backend": a.backend,
            "server_url": a.server_url,
            "api_model_name": a.api_model_name,
            "skip_existing": bool(a.skip_existing)}


def _resolve_predictions_dir(a, default: Path) -> Path:
    """Resolved predictions dir: explicit --predictions-dir, else the canonical default."""
    raw = getattr(a, "predictions_dir", "") or ""
    return Path(raw) if raw else default


def _orchestrate_run(a) -> int:
    """Run the four-stage pipeline (download -> infer -> score -> publish).

    For --stage all the stages execute in order, threading artifacts and ONE
    inference config into both infer and publish (so provenance records exactly
    what ran). Single-stage values dispatch to just that stage.
    """
    stage = a.stage
    img_dir = dataset_dir(a.version) / "images"
    default_preds = predictions_dir(a.model_id, a.platform)
    predictions = _resolve_predictions_dir(a, default_preds)
    run_stats_path = predictions / "_run_stats.json"
    infer_config = _infer_config_from_args(a)

    if stage == "download":
        stage_download(a.version, a.revision)
        return 0

    if stage == "infer":
        stage_infer(adapter_path=Path(a.adapter), img_dir=img_dir,
                    out_dir=predictions, platform=a.platform, config=infer_config)
        return 0

    if stage == "score":
        backend = get_backend(a.platform)
        stage_score(backend=backend, predictions_dir=predictions, version=a.version,
                    cdm=a.cdm, run_stats_path=run_stats_path,
                    scoring_config=(Path(a.scoring_config) if a.scoring_config else None),
                    dataset_dir=(Path(a.dataset_dir) if a.dataset_dir else None))
        return 0

    if stage == "publish":
        # Explicit metric_result only — never guess a path. adapter_command is the
        # user-supplied --adapter-command (default "" — no infer ran in this
        # invocation; use `run --stage all` for the auto-recorded adapter argv).
        if not a.metric_result:
            raise SystemExit("run --stage publish requires --metric-result")
        metric_path = Path(a.metric_result)
        stage_publish(
            model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
            run_stats_path=run_stats_path, metric_result_path=metric_path,
            results_dir=Path(a.results_dir), git_commit=a.git_commit,
            engine_version=omnidocbench_rocm.__version__,
            adapter_command=a.adapter_command, predictions_dir=predictions,
            requested_backend=a.backend, server_url=a.server_url,
            api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
            dataset_manifest_path=a.dataset_manifest, dataset_revision=a.revision,
            ground_truth_sha256=a.gt_sha256,
            prediction_source_commit=a.prediction_source_commit,
            prediction_source_command=a.prediction_source_command,
            prediction_source_run_manifest=a.prediction_source_run_manifest,
            migration_type=a.migration_type)
        return 0

    # stage == "all": full pipeline in order.
    stage_download(a.version, a.revision)
    infer_result = stage_infer(adapter_path=Path(a.adapter), img_dir=img_dir,
                               out_dir=predictions, platform=a.platform, config=infer_config)
    backend = get_backend(a.platform)
    metric_result_path = stage_score(
        backend=backend, predictions_dir=predictions, version=a.version, cdm=a.cdm,
        run_stats_path=run_stats_path,
        scoring_config=(Path(a.scoring_config) if a.scoring_config else None),
        dataset_dir=(Path(a.dataset_dir) if a.dataset_dir else None))
    if a.adapter_command:
        print("[run] note: using user-supplied --adapter-command; overriding "
              "the recorded adapter argv.", file=sys.stderr)
        adapter_command = a.adapter_command
    else:
        adapter_command = shlex.join(infer_result.adapter_argv)
    stage_publish(
        model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
        run_stats_path=run_stats_path, metric_result_path=metric_result_path,
        results_dir=Path(a.results_dir), git_commit=a.git_commit,
        engine_version=omnidocbench_rocm.__version__,
        adapter_command=adapter_command, predictions_dir=predictions,
        requested_backend=a.backend, server_url=a.server_url,
        api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
        dataset_manifest_path=a.dataset_manifest, dataset_revision=a.revision,
        ground_truth_sha256=a.gt_sha256,
        prediction_source_commit=(a.prediction_source_commit or a.git_commit),
        prediction_source_command=(a.prediction_source_command or adapter_command),
        prediction_source_run_manifest=a.prediction_source_run_manifest,
        migration_type=(a.migration_type or "native-platform-run"))
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
    ip.add_argument("--backend", default="")
    ip.add_argument("--server-url", default="")
    ip.add_argument("--api-model-name", default="")
    ip.add_argument("--skip-existing", action="store_true")

    sc = sub.add_parser("score")
    sc.add_argument("--platform", required=True)
    sc.add_argument("--predictions-dir", required=True)
    sc.add_argument("--version", default="v16")
    sc.add_argument("--cdm", action="store_true")
    sc.add_argument("--run-stats", required=True)
    sc.add_argument("--scoring-config", default="")
    sc.add_argument("--dataset-dir", default="")

    pu = sub.add_parser("publish")
    pu.add_argument("--model-id", required=True)
    pu.add_argument("--platform", required=True)
    pu.add_argument("--version", default="v16")
    pu.add_argument("--cdm", action="store_true")
    pu.add_argument("--run-stats", required=True)
    pu.add_argument("--metric-result", required=True)
    pu.add_argument("--results-dir", required=True)
    pu.add_argument("--predictions-dir", required=True,
                    help="real predictions dir (where the .md files live)")
    pu.add_argument("--git-commit", required=True)
    pu.add_argument("--adapter-command", required=True)
    pu.add_argument("--server-url", default="")
    pu.add_argument("--api-model-name", default="")
    pu.add_argument("--scoring-config", default="")
    pu.add_argument("--dataset-manifest", default="")
    pu.add_argument("--dataset-revision", required=True)
    pu.add_argument("--backend", default="",
                    help="expected adapter backend; checked against _run_stats.json['engine']")
    pu.add_argument("--gt-sha256", default="",
                    help="ground-truth JSON SHA256 recorded in the dataset identity")
    pu.add_argument("--prediction-source-commit", default="",
                    help="provenance: commit that produced the predictions")
    pu.add_argument("--prediction-source-command", default="",
                    help="provenance: command that produced the predictions")
    pu.add_argument("--prediction-source-run-manifest", default="",
                    help="provenance: path to the legacy run_manifest.json")
    pu.add_argument("--migration-type", default="",
                    help="provenance: e.g. legacy_predictions_to_platform_artifacts")

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
    rn.add_argument("--backend", default="",
                    help="adapter backend to request (e.g. vlm-vllm, pipeline); empty = adapter default")
    rn.add_argument("--skip-existing", action="store_true",
                    help="infer only: skip pages whose .md already exists")
    rn.add_argument("--predictions-dir", default="",
                    help="predictions dir; defaults to predictions_dir(model_id, platform)")
    rn.add_argument("--scoring-config", default="")
    rn.add_argument("--dataset-manifest", default="")
    rn.add_argument("--dataset-dir", default="")
    rn.add_argument("--metric-result", default="",
                    help="publish stage: explicit metric_result.json (required for --stage publish)")
    rn.add_argument("--gt-sha256", default="",
                    help="provenance: ground-truth JSON SHA256 for the dataset identity")
    rn.add_argument("--prediction-source-commit", default="")
    rn.add_argument("--prediction-source-command", default="")
    rn.add_argument("--prediction-source-run-manifest", default="")
    rn.add_argument("--migration-type", default="")

    cf = sub.add_parser("conformance")
    cf.add_argument("repo_path")

    vb = sub.add_parser("validate-bundle")
    vb.add_argument("results_dir", help="results/omnidocbench/<version>/<platform>/ bundle dir")
    vb.add_argument("--model-card", default="",
                    help="optional model_card.json to cross-check Overall + model_id")
    vb.add_argument("--registry", default="",
                    help="optional hub/registry.yaml to cross-check Overall + badge")

    ls = sub.add_parser("list",
                        help="list catalogued models + their best badge (ADR-0005 discovery)")
    ls.add_argument("--registry", default="hub/registry.yaml",
                    help="path to registry.yaml (default: hub/registry.yaml)")
    ls.add_argument("--format", default="text", choices=["text", "json"],
                    help="output format (default: text)")

    dr = sub.add_parser("doctor",
                        help="check a repo's readiness: conformance + adapter_config hint")
    dr.add_argument("repo_path")

    # ADR-0007: migrate a v1 model_card.json to v2 (idempotent, no guessing).
    mmc = sub.add_parser("migrate-model-card",
                         help="migrate a v1 model_card.json to Model Card v2")
    mmc.add_argument("input")
    mmc.add_argument("--check", action="store_true",
                     help="dry-run: exit 0 if already v2, 1 if migration needed / invalid")
    mmc.add_argument("--in-place", action="store_true")
    mmc.add_argument("--output", default="")

    # ADR-0009: validate a rocmdoc.yaml manifest (+ optional result alignment).
    mfs = sub.add_parser("manifest", help="validate a rocmdoc.yaml capability manifest")
    mfs.add_argument("manifest_path")
    mfs.add_argument("--card", default="",
                     help="model_card.json (v1 or v2) to check results align to declared capabilities")

    # ADR-0010: classify a license into the open-source taxonomy.
    lc = sub.add_parser("license-classify", help="classify an SPDX id / license name")
    lc.add_argument("license")

    # ADR-0011: run a behavioral conformance profile against a standard CLI.
    cfp = sub.add_parser("conformance-profiles", help="run a behavioral conformance profile")
    from .conformance_profiles import PROFILE_ORDER as _PROFILES
    cfp.add_argument("profile", choices=list(_PROFILES))
    cfp.add_argument("--cli", default="", help="path to the model's standard-CLI entrypoint")
    cfp.add_argument("--img-dir", default="")
    cfp.add_argument("--out-dir", default="")
    cfp.add_argument("--result-record", default="",
                     help="path to a result_record JSON (for reproducible-score)")
    cfp.add_argument("--bundle-dir", default="")
    cfp.add_argument("--backend", default="")

    a = p.parse_args(argv)

    if a.cmd == "cdm":
        get_backend(a.platform).provision_cdm()
        return 0
    if a.cmd == "dataset":
        stage_download(a.version, a.revision)
        return 0
    if a.cmd == "infer":
        stage_infer(adapter_path=Path(a.adapter), img_dir=Path(a.img_dir),
                    out_dir=Path(a.out_dir), platform=a.platform,
                    config=_infer_config_from_args(a))
        return 0
    if a.cmd == "score":
        b = get_backend(a.platform)
        stage_score(backend=b, predictions_dir=Path(a.predictions_dir),
                    version=a.version, cdm=a.cdm,
                    run_stats_path=Path(a.run_stats),
                    scoring_config=(Path(a.scoring_config) if a.scoring_config else None),
                    dataset_dir=(Path(a.dataset_dir) if a.dataset_dir else None))
        return 0
    if a.cmd == "publish":
        stage_publish(
            model_id=a.model_id, platform=a.platform, version=a.version, cdm=a.cdm,
            run_stats_path=Path(a.run_stats), metric_result_path=Path(a.metric_result),
            results_dir=Path(a.results_dir), git_commit=a.git_commit,
            engine_version=omnidocbench_rocm.__version__,
            adapter_command=a.adapter_command, predictions_dir=Path(a.predictions_dir),
            requested_backend=a.backend, server_url=a.server_url,
            api_model_name=a.api_model_name, scoring_config_path=a.scoring_config,
            dataset_manifest_path=a.dataset_manifest, dataset_revision=a.dataset_revision,
            ground_truth_sha256=a.gt_sha256,
            prediction_source_commit=a.prediction_source_commit,
            prediction_source_command=a.prediction_source_command,
            prediction_source_run_manifest=a.prediction_source_run_manifest,
            migration_type=a.migration_type)
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
    if a.cmd == "validate-bundle":
        report = validate_bundle(Path(a.results_dir),
                                 model_card=(a.model_card or None),
                                 registry=(a.registry or None))
        if report.ok:
            print("CONFORMANT"); return 0
        print("NON-CONFORMANT:")
        for f in report.failures:
            print(" -", f)
        return 1
    if a.cmd == "list":
        # Discovery layer (ADR-0005): print each model_id + best badge + license.
        # Reuses the package registry loader + _best_badge — same model the hub
        # renders from, so the catalog and the hub never drift.
        import json as _json

        from .registry import _best_badge, generate_registry

        rows = generate_registry(a.registry)
        rows = [{"model_id": r.get("model_id"), "repo": r.get("repo"),
                 "license": r.get("license"), "best_badge": _best_badge(r)} for r in rows]
        if a.format == "json":
            print(_json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f"{r['model_id']:<24} {r['best_badge']:<16} {r.get('license') or '—'}")
        return 0
    if a.cmd == "doctor":
        # ADR-0005 readiness: run the conformance gate, then surface a best-effort
        # hint on whether adapter/adapter_config.py exists. Mirrors the
        # ``conformance`` subcommand's report handling but with a READY/NOT READY
        # verdict + readiness hint instead of a bare CONFORMANT/NON-CONFORMANT.
        report = check_repo(Path(a.repo_path))
        if report.ok:
            print("READY: repo is conformant.")
            # best-effort readiness hint
            cfg = Path(a.repo_path) / "adapter" / "adapter_config.py"
            print("  adapter_config.py present:", cfg.exists())
            return 0
        print("NOT READY:")
        for f in report.failures:
            print(" -", f)
        return 1
    if a.cmd == "migrate-model-card":
        # ADR-0007: v1 -> v2 migration (idempotent, machine-readable report).
        import json as _json
        from .migrate import migrate_file
        v2, report, exit_code = migrate_file(a.input, output=(a.output or None),
                                             in_place=a.in_place, check=a.check)
        if a.check:
            print(_json.dumps(report, ensure_ascii=False, indent=2))
            return exit_code
        if not a.in_place and not a.output:
            sys.stdout.write(_json.dumps(v2, ensure_ascii=False, indent=2) + "\n")
        sys.stderr.write("[migrate] " + _json.dumps(report, ensure_ascii=False) + "\n")
        return exit_code
    if a.cmd == "manifest":
        # ADR-0009: manifest validation + optional result alignment (no faking support).
        import json as _json
        from .manifest import load_manifest, validate_manifest, check_result_alignment
        mf = load_manifest(a.manifest_path)
        problems = validate_manifest(mf)
        if a.card:
            card = _json.loads(Path(a.card).read_text(encoding="utf-8"))
            # accept v2 directly; migrate v1 on the fly for the alignment check
            if card.get("schema_version") != 2:
                from .migrate import migrate_v1_to_v2
                card, _ = migrate_v1_to_v2(card)
            problems += check_result_alignment(mf, card)
        if problems:
            print("MANIFEST INVALID:")
            for f in problems:
                print(" -", f)
            return 1
        print("MANIFEST VALID")
        return 0
    if a.cmd == "license-classify":
        import json as _json
        from .license_class import build_license_record
        rec = build_license_record(spdx=a.license)
        print(_json.dumps(rec, ensure_ascii=False, indent=2))
        return 0
    if a.cmd == "conformance-profiles":
        # ADR-0011: behavioral profile against a standard CLI or a result record.
        import json as _json
        from .conformance_profiles import check_profile
        rr = None
        if a.result_record:
            rr = _json.loads(Path(a.result_record).read_text(encoding="utf-8"))
        report = check_profile(a.profile, cli_path=(a.cli or None),
                               img_dir=(a.img_dir or None), out_dir=(a.out_dir or None),
                               requested_backend=a.backend, result_record=rr,
                               bundle_dir=(a.bundle_dir or None))
        if report.ok:
            print(f"CONFORMANT: profile {a.profile!r} passed"); return 0
        print(f"NON-CONFORMANT: profile {a.profile!r}")
        for f in report.failures:
            print(" -", f)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
