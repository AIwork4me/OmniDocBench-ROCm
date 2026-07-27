"""Behavioral conformance profiles (ADR-0011).

v1 conformance (:func:`conformance.check_repo`) was STRUCTURAL — files exist,
README sections present, schema-valid. v2 adds BEHAVIORAL profiles that actually
RUN a model's standard CLI as a subprocess and check how it behaves:

    base                          the CLI exists and speaks the contract (version)
    runtime-core                  version + capabilities + doctor --json, pure JSON,
                                  offline-capable, standard exit codes
    benchmark-omnidocbench-v16    full-set parse on OmniDocBench v1.6, valid cli_result
    reproducible-score            provenance-complete + artifact hashes valid

Profiles are CUMULATIVE (each implies the previous). The central repo runs them
against fake-CLI fixtures in CI (no GPU, no model runtime imported). Real
per-model adapters gain the standard CLI via the :mod:`cli_bridge` shim or by
implementing the contract directly.

Usage::

    from omnidocbench_rocm.conformance_profiles import check_profile, PROFILES
    report = check_profile("runtime-core", cli_path="path/to/cli.py",
                            img_dir="imgs", out_dir=tmp)
    if not report.ok: print(report.failures)
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from . import cli_contract as cc
from .conformance import ConformanceReport

PROFILE_ORDER = ("base", "runtime-core", "benchmark-omnidocbench-v16", "reproducible-score")
PROFILES = set(PROFILE_ORDER)


def run_cli(cli_path: Path | str, args: list[str], *, cwd: str | None = None,
            timeout: float = 60, env: dict | None = None) -> cc.CLIRun:
    """Invoke a CLI as a subprocess (R1: the engine never imports the adapter).

    Uses ``sys.executable`` so ``.py`` CLIs run under the same interpreter. The
    subprocess inherits a copy of os.environ unless ``env`` is given.
    """
    cmd = [sys.executable, str(cli_path), *args]
    proc_env = dict(os.environ)
    if env:
        proc_env.update(env)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=cwd, env=proc_env)
    return cc.CLIRun(stdout=proc.stdout, stderr=proc.stderr, returncode=proc.returncode)


# --- individual behavioral checks -------------------------------------------

def _chk_version(report: ConformanceReport, cli_path: Path) -> None:
    run = run_cli(cli_path, ["version", "--json"])
    if run.returncode != cc.EXIT_OK:
        report.add(f"version --json: expected exit 0, got {run.returncode}")
        return
    obj, err = cc.parse_json_stdout(run)
    if err:
        report.add(f"version --json: {err} (stdout was not pure JSON)")
        return
    for p in cc.validate_version_output(obj):
        report.add(p)


def _chk_json_purity(report: ConformanceReport, cli_path: Path, args: list[str], label: str) -> dict | None:
    run = run_cli(cli_path, args)
    obj, err = cc.parse_json_stdout(run)
    if err:
        report.add(f"{label}: {err}")
        return None
    return obj


def _chk_capabilities(report: ConformanceReport, cli_path: Path) -> None:
    obj = _chk_json_purity(report, cli_path, ["capabilities", "--json"], "capabilities --json")
    if obj is None:
        return
    for p in cc.validate_capabilities_output(obj):
        report.add(p)
    plats = obj.get("platforms") or []
    if not plats:
        report.add("capabilities --json: declares no platforms")


def _chk_doctor(report: ConformanceReport, cli_path: Path) -> None:
    obj = _chk_json_purity(report, cli_path, ["doctor", "--json"], "doctor --json")
    if obj is None:
        return
    for p in cc.validate_doctor_output(obj):
        report.add(p)


def _chk_offline(report: ConformanceReport, cli_path: Path) -> None:
    """The CLI must be usable with no network (OMNIDOCS_OFFLINE=1).

    A model CLI that phones home on capabilities/doctor is not reproducible in CI
    or air-gapped environments. Fakes ignore the network entirely; this asserts
    the contract surface respects the offline flag.
    """
    run = run_cli(cli_path, ["capabilities", "--json"], env={"OMNIDOCS_OFFLINE": "1"})
    if run.returncode != cc.EXIT_OK:
        report.add(f"offline: capabilities --json failed under OMNIDOCS_OFFLINE=1 (exit {run.returncode})")
        return
    obj, err = cc.parse_json_stdout(run)
    if err:
        report.add(f"offline: {err}")


def _chk_full_parse(report: ConformanceReport, cli_path: Path, img_dir: Path,
                    out_dir: Path, requested_backend: str = "") -> None:
    args = ["parse", "--img-dir", str(img_dir), "--out-dir", str(out_dir),
            "--platform", "linux-rocm", "--benchmark", "omnidocbench-v16", "--json"]
    if requested_backend:
        args += ["--backend", requested_backend]
    run = run_cli(cli_path, args)
    if run.returncode not in (cc.EXIT_OK, cc.EXIT_PARTIAL):
        report.add(f"parse: expected exit 0/1, got {run.returncode} (stderr: {run.stderr.strip()[:200]})")
        return
    obj, err = cc.parse_json_stdout(run)
    if err:
        report.add(f"parse: {err}")
        return
    for p in cc.validate_result_output(obj):
        report.add(p)
    # page_count must equal the number of images in img_dir (full-set honesty)
    n_imgs = sum(1 for _ in img_dir.iterdir()) if img_dir.is_dir() else 0
    if n_imgs and obj.get("page_count") not in (n_imgs, None):
        report.add(f"parse: page_count {obj.get('page_count')} != {n_imgs} images in img-dir")
    # backend match
    bm = cc.check_backend_match(obj, requested_backend)
    if bm:
        report.add(f"parse: {bm}")
    # status/exit-code consistency: partial status -> exit 1, ok status -> exit 0
    status = obj.get("status")
    if status == "ok" and run.returncode != cc.EXIT_OK:
        report.add(f"parse: status ok but exit {run.returncode}")
    if status == "partial" and run.returncode != cc.EXIT_PARTIAL:
        report.add(f"parse: status partial but exit {run.returncode} (expected 1)")


def check_partial_success(cli_path: Path | str, img_dir: Path | str,
                          out_dir: Path | str) -> ConformanceReport:
    """Standalone R2 robustness check: a CLI that fails some pages must NOT crash.

    Runs ``parse`` and asserts the run completed with status ``partial`` + exit 1
    (never a crash / exit 5). Used with a deliberately-failing fixture (e.g. the
    ``partial`` fake CLI); a conformant adapter continues past per-page failures.
    """
    report = ConformanceReport()
    _probe_partial_success(report, Path(cli_path), Path(img_dir), Path(out_dir))
    return report


def _probe_partial_success(report: ConformanceReport, cli_path: Path, img_dir: Path,
                            out_dir: Path) -> None:
    """A CLI that fails some pages must: status=partial, exit 1, NOT crash (R2).

    The fake 'partial' fixture fails every other page; the run must still complete
    and emit a valid cli_result rather than raising.
    """
    run = run_cli(cli_path, ["parse", "--img-dir", str(img_dir), "--out-dir", str(out_dir),
                             "--platform", "linux-rocm", "--json"])
    if run.returncode == cc.EXIT_FATAL:
        report.add("partial-success: CLI crashed (exit 5) instead of continuing past failed pages (R2)")
        return
    if run.returncode != cc.EXIT_PARTIAL:
        report.add(f"partial-success: expected exit 1 for a partial run, got {run.returncode}")
    obj, err = cc.parse_json_stdout(run)
    if err:
        report.add(f"partial-success: {err}")
        return
    if obj.get("status") != "partial":
        report.add(f"partial-success: expected status 'partial', got {obj.get('status')!r}")
    if obj.get("failed", 0) <= 0:
        report.add("partial-success: reported no failed pages for a partial run")


def _check_provenance_complete(report: ConformanceReport, result_record: dict) -> None:
    prov = result_record.get("provenance") or {}
    missing = [k for k in ("created_at_utc", "git_commit") if not prov.get(k)]
    if missing:
        report.add(f"provenance: missing {missing} (evidence-complete requires these)")
    arts = result_record.get("artifacts") or {}
    if not arts:
        report.add("provenance: no artifact references recorded")
    # RFC3339 check on created_at_utc
    ts = prov.get("created_at_utc")
    if ts:
        from .schema import iter_validation_errors
        probe = {"result_id": result_record.get("result_id", "x"),
                 "status": result_record.get("status", "valid"),
                 "assurance": result_record.get("assurance", "submitted"),
                 "benchmark": result_record.get("benchmark", {"name": "OmniDocBench", "version": "v1.6"}),
                 "metrics": result_record.get("metrics", {"overall": None}),
                 "provenance": {"created_at_utc": ts, "git_commit": prov.get("git_commit", "")}}
        errs = iter_validation_errors("result_record", probe)
        for e in errs:
            if "created_at_utc" in e or "date-time" in e:
                report.add(f"provenance: created_at_utc not RFC3339: {ts!r}")


def _check_artifact_hashes(report: ConformanceReport, result_record: dict, *,
                           bundle_dir: Path | None = None) -> None:
    arts = result_record.get("artifacts") or {}
    for key, val in arts.items():
        if not key.endswith("_sha256") or not isinstance(val, str):
            continue
        if not (val.startswith("sha256:") and len(val) == 7 + 64):
            report.add(f"artifact hash: {key}={val!r} is not a sha256:<64hex> digest")
            continue
        # If the corresponding artifact path is present and resolves, verify the hash.
        path_key = key[: -len("_sha256")]
        path_val = arts.get(path_key)
        if path_val and bundle_dir is not None:
            p = Path(path_val)
            if not p.is_absolute():
                p = bundle_dir / p
            if p.exists() and p.is_file():
                actual = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
                if actual != val:
                    report.add(f"artifact hash: {key} does not match content of {path_val}")


# --- profile dispatch --------------------------------------------------------

def check_profile(profile: str, *, cli_path: Path | str | None = None,
                  img_dir: Path | str | None = None, out_dir: Path | str | None = None,
                  requested_backend: str = "", result_record: dict | None = None,
                  bundle_dir: Path | str | None = None) -> ConformanceReport:
    """Run one behavioral conformance profile. Returns a ConformanceReport.

    ``cli_path``/``img_dir``/``out_dir`` feed the CLI-running profiles;
    ``result_record``/``bundle_dir`` feed reproducible-score. Missing inputs for
    a non-applicable check are skipped (not failures).
    """
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile!r} (expected one of {PROFILE_ORDER})")
    report = ConformanceReport()
    cli = Path(cli_path) if cli_path else None
    imgs = Path(img_dir) if img_dir else None
    out = Path(out_dir) if out_dir else None

    if profile in ("base", "runtime-core", "benchmark-omnidocbench-v16"):
        if cli is None or not cli.exists():
            report.add(f"{profile}: cli_path not found: {cli_path!r}")
            return report
        _chk_version(report, cli)

    if profile in ("runtime-core", "benchmark-omnidocbench-v16"):
        _chk_capabilities(report, cli)
        _chk_doctor(report, cli)
        _chk_offline(report, cli)

    if profile == "benchmark-omnidocbench-v16":
        if imgs is None or not imgs.is_dir():
            report.add("benchmark-omnidocbench-v16: img_dir not provided / not a directory")
        else:
            out = out or (imgs.parent / "out")
            out.mkdir(parents=True, exist_ok=True)
            _chk_full_parse(report, cli, imgs, out, requested_backend=requested_backend)

    if profile == "reproducible-score":
        if result_record is None:
            report.add("reproducible-score: result_record not provided")
        else:
            _check_provenance_complete(report, result_record)
            _check_artifact_hashes(report, result_record,
                                    bundle_dir=(Path(bundle_dir) if bundle_dir else None))

    return report
