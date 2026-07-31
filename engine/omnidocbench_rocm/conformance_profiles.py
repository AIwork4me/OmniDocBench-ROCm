"""Behavioral conformance profiles (ADR-0011 + Round-2 ADR-0018 semantics).

v2 profiles were STRUCTURAL/BEHAVIORAL and *cumulative* but their NAMES lied:
``reproducible-score`` only checked that artifact hashes were intact — it never
ran a scorer. Round-2 (§4) fixes the semantics with an explicit, programmatic
ladder where each name means exactly what it says:

    base                          the CLI exists and speaks the contract (version)
    runtime-contract              version + capabilities + doctor --json, pure JSON,
                                  offline-capable, standard exit codes
    benchmark-contract            full-set parse on OmniDocBench v1.6, valid cli_result
    evidence-integrity            required evidence files + schema + artifact hash +
                                  source reference + page count + result_id +
                                  run_spec_hash + requested/actual backend + identity +
                                  producer_assurance — does NOT claim a score was replayed
    score-reproduction            REALLY runs a fixed scorer over fixed predictions and
                                  diffs the metrics (a fixture scorer is OK for CI but a
                                  fixture pass does NOT promote platform_review)
    inference-reproduction        REALLY re-runs inference on AMD HW (GPU; NOT_RUN when
                                  RUN_GPU=false — never reported as passed)
    cross-hardware-reproduction   reproduced on a SECOND AMD GPU/arch (GPU; NOT_RUN)

Profiles are CUMULATIVE via an explicit dependency graph
(:func:`profile_includes` / :func:`accumulate`), not just documented as such.

Back-compat: the v2 names ``runtime-core`` / ``benchmark-omnidocbench-v16`` /
``reproducible-score`` remain valid as ALIASES of their renamed canonicals, so
existing repos and tests are unaffected.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

from . import cli_contract as cc
from . import run_spec as rs
from .conformance import ConformanceReport

# --- v2 names (UNCHANGED — existing repos/tests depend on these exactly) -----
PROFILE_ORDER = ("base", "runtime-core", "benchmark-omnidocbench-v16", "reproducible-score")
PROFILES = set(PROFILE_ORDER)

# --- Round-2 canonical ladder (ADR-0018) -------------------------------------
PROFILE_LADDER = (
    "base",
    "runtime-contract",
    "benchmark-contract",
    "evidence-integrity",
    "score-reproduction",
    "inference-reproduction",
    "cross-hardware-reproduction",
)
LADDER_PROFILES = set(PROFILE_LADDER)
ALL_PROFILES = PROFILES | LADDER_PROFILES

# v2 name -> Round-2 canonical (alias resolution; old names keep working).
ALIAS = {
    "runtime-core": "runtime-contract",
    "benchmark-omnidocbench-v16": "benchmark-contract",
    "reproducible-score": "evidence-integrity",
}


def _resolve(name: str) -> str:
    """Map any accepted profile name (v2 alias or Round-2 canonical) to its
    Round-2 canonical on the ladder."""
    return ALIAS.get(name, name)


def profile_rank(name: str) -> int:
    """Ladder index of a profile's canonical (higher = deeper reproduction)."""
    return PROFILE_LADDER.index(_resolve(name))


def profile_includes(lower: str, higher: str) -> bool:
    """True iff the ``higher`` profile subsumes ``lower`` (programmatic graph).

    e.g. evidence-integrity includes benchmark-contract includes runtime-contract.
    """
    return profile_rank(lower) <= profile_rank(higher)


def run_cli(cli_path: Path | str, args: list[str], *, cwd: str | None = None,
            timeout: float = 60, env: dict | None = None) -> cc.CLIRun:
    """Invoke a CLI as a subprocess (R1: the engine never imports the adapter).

    Uses ``sys.executable`` so ``.py`` CLIs run under the same interpreter. The
    subprocess inherits a copy of os.environ unless ``env`` is given. Setting
    ``ROCMDOC_NETWORK_DENY=1`` in ``env`` is the convention by which a conformant
    CLI fails CLOSED on network (stronger than merely honoring an offline flag).
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
    """The CLI must be usable with no network.

    Beyond the v2 ``OMNIDOCS_OFFLINE=1`` flag we also set ``ROCMDOC_NETWORK_DENY=1``
    — the convention by which a conformant CLI fails CLOSED on network. (Truly
    blocking an arbitrary subprocess's sockets needs a network namespace, which
    is a deployment concern; for in-process central paths use
    :func:`assert_no_network`, which monkeypatches the socket for real.)
    """
    run = run_cli(cli_path, ["capabilities", "--json"],
                  env={"OMNIDOCS_OFFLINE": "1", "ROCMDOC_NETWORK_DENY": "1"})
    if run.returncode != cc.EXIT_OK:
        report.add(f"offline: capabilities --json failed under OMNIDOCS_OFFLINE=1/ROCMDOC_NETWORK_DENY=1 (exit {run.returncode})")
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
    """Standalone R2 robustness check: a CLI that fails some pages must NOT crash."""
    report = ConformanceReport()
    _probe_partial_success(report, Path(cli_path), Path(img_dir), Path(out_dir))
    return report


def _probe_partial_success(report: ConformanceReport, cli_path: Path, img_dir: Path,
                            out_dir: Path) -> None:
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


def _check_identity(report: ConformanceReport, result_record: dict) -> None:
    """Round-2 evidence-integrity identity invariants (ADR-0015).

    Only flags results that CARRY a run_spec but mis-state it. A v2 record with no
    run_spec is legacy-clean here (it is barred from default comparison tables by
    the track layer, not by this check). NEVER claims a score was replayed.
    """
    spec = result_record.get("run_spec")
    if isinstance(spec, dict):
        declared = result_record.get("run_spec_hash")
        if declared:
            actual = rs.run_spec_hash(spec)
            if actual != declared:
                report.add(f"identity: run_spec_hash {declared!r} != recompute {actual!r}")
        bad = rs.uses_default_sentinel(spec)
        if bad:
            report.add(f"identity: run_spec uses forbidden 'default' sentinel for {bad}")
        missing = rs.missing_critical(spec)
        if missing:
            report.add(f"identity: run_spec missing critical fields {missing} "
                        "(state them explicitly, even as 'unknown')")
    # a valid result must not carry backend/precision == 'default' at the
    # implementation level either (the v2 anti-pattern).
    impl = result_record.get("implementation") or {}
    for k in ("backend", "precision"):
        if impl.get(k) == rs.DEFAULT:
            report.add(f"identity: implementation.{k}=='default' is forbidden for a valid result")


def _check_source_reference(report: ConformanceReport, result_record: dict) -> None:
    """If a result claims an immutable source, it must be a real 40-hex ref."""
    src = result_record.get("source")
    if not src:
        return
    from . import source_import as SI
    commit = src.get("commit") if isinstance(src, dict) else None
    if commit and not SI.is_immutable_commit(commit):
        report.add(f"identity: source.commit {commit!r} is not a 40-hex immutable SHA")


# --- score reproduction: REAL scorer replay (Round-2 §4.3) -------------------

def run_scorer_replay(scorer_argv: list[str], *, expected_metrics: dict,
                      tolerance: float = 0.01, cwd: str | None = None,
                      timeout: float = 120, env: dict | None = None) -> dict:
    """Run a FIXED scorer over FIXED predictions and diff the reproduced metrics.

    Returns a replay record:
        {reproduction_command, exit_code, reproduced, expected, diff, passed,
         scorer_revision, environment}
    This is a CONFORMANCE check (did the replay reproduce?), NOT a platform_review
    promotion — filing the returned record as a review_artifact is a separate,
    auditable review step that carries this evidence. A fixture scorer pass does
    NOT raise any result's platform_review.
    """
    proc_env = dict(os.environ)
    if env:
        proc_env.update(env)
    proc = subprocess.run(scorer_argv, capture_output=True, text=True,
                          timeout=timeout, cwd=cwd, env=proc_env)
    replay: dict = {
        "reproduction_command": scorer_argv,
        "exit_code": proc.returncode,
        "scorer_stdout": proc.stdout.strip()[:4000],
        "scorer_stderr": proc.stderr.strip()[:2000],
    }
    reproduced: dict = {}
    if proc.returncode == 0:
        try:
            obj = json.loads(proc.stdout.strip())
            reproduced = obj.get("metrics", obj) if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            replay["parse_error"] = "scorer stdout was not JSON"
    diff: dict = {}
    passed = proc.returncode == 0 and bool(reproduced)
    for k, want in (expected_metrics or {}).items():
        got = reproduced.get(k)
        if got is None:
            diff[k] = {"expected": want, "got": None}; passed = False
        elif isinstance(want, (int, float)) and isinstance(got, (int, float)):
            if abs(got - want) > tolerance:
                diff[k] = {"expected": want, "got": got, "delta": got - want}; passed = False
        elif got != want:
            diff[k] = {"expected": want, "got": got}; passed = False
    replay.update({"reproduced": reproduced, "expected": expected_metrics,
                    "diff": diff, "passed": passed})
    return replay


def _check_scorer_replay(report: ConformanceReport, *, scorer_argv: list[str] | None,
                         expected_metrics: dict | None, tolerance: float = 0.01,
                         cwd: str | None = None) -> dict | None:
    """score-reproduction profile check. NOT_RUN (never 'passed') without inputs."""
    if not scorer_argv or expected_metrics is None:
        report.mark_not_run("score-reproduction requires a fixed scorer command + expected metrics")
        return None
    replay = run_scorer_replay(scorer_argv, expected_metrics=expected_metrics,
                                tolerance=tolerance, cwd=cwd)
    if not replay["passed"]:
        report.add(f"score-reproduction: scorer replay did not reproduce metrics "
                   f"(exit {replay['exit_code']}, diff={replay['diff']})")
    return replay


# --- offline network denial (in-process, REAL block) ------------------------

class _NetworkBlocked(OSError):
    pass


def assert_no_network(fn, *args, **kwargs):
    """Run ``fn`` with outbound network REALLY blocked (in-process).

    Replaces ``socket.socket`` with a subclass whose ``connect`` raises, so any
    attempt to open a remote connection fails. Used to prove the central
    import/validate paths never phone home. (Local bind/listen still works.)
    Restores the original ``socket.socket`` on return/raise. Returns fn's result.
    """
    _real_socket = socket.socket

    class _BlockingSocket(_real_socket):
        def connect(self, address):  # type: ignore[override]
            raise _NetworkBlocked(f"network blocked by assert_no_network: {address}")

    saved = socket.socket
    socket.socket = _BlockingSocket  # type: ignore[assignment]
    try:
        return fn(*args, **kwargs)
    finally:
        socket.socket = saved  # type: ignore[assignment]


# --- profile dispatch --------------------------------------------------------

# Which profiles need a CLI vs a result_record vs scorer inputs.
_CLI_PROFILES = {"base", "runtime-contract", "benchmark-contract"}
_RESULT_PROFILES = {"evidence-integrity"}


def check_profile(profile: str, *, cli_path: Path | str | None = None,
                  img_dir: Path | str | None = None, out_dir: Path | str | None = None,
                  requested_backend: str = "", result_record: dict | None = None,
                  bundle_dir: Path | str | None = None,
                  scorer_argv: list[str] | None = None,
                  expected_metrics: dict | None = None,
                  tolerance: float = 0.01) -> ConformanceReport:
    """Run one behavioral conformance profile. Returns a ConformanceReport.

    Accepts both Round-2 canonical names and v2 aliases. Missing inputs for a
    non-applicable check are skipped (NOT failures) — except GPU profiles, which
    are NOT_RUN (and therefore never reported as passed) when their inputs are
    absent.
    """
    if profile not in ALL_PROFILES:
        raise ValueError(f"unknown profile: {profile!r} (expected one of "
                         f"{sorted(ALL_PROFILES)})")
    report = ConformanceReport()
    canon = _resolve(profile)
    cli = Path(cli_path) if cli_path else None
    imgs = Path(img_dir) if img_dir else None
    out = Path(out_dir) if out_dir else None

    if canon in _CLI_PROFILES:
        if cli is None or not cli.exists():
            report.add(f"{profile}: cli_path not found: {cli_path!r}")
            return report
        _chk_version(report, cli)

    if canon in ("runtime-contract", "benchmark-contract"):
        _chk_capabilities(report, cli)
        _chk_doctor(report, cli)
        _chk_offline(report, cli)

    if canon == "benchmark-contract":
        if imgs is None or not imgs.is_dir():
            report.add(f"{profile}: img_dir not provided / not a directory")
        else:
            out = out or (imgs.parent / "out")
            out.mkdir(parents=True, exist_ok=True)
            _chk_full_parse(report, cli, imgs, out, requested_backend=requested_backend)

    if canon == "evidence-integrity":
        if result_record is None:
            report.add(f"{profile}: result_record not provided")
        else:
            _check_provenance_complete(report, result_record)
            _check_artifact_hashes(report, result_record,
                                    bundle_dir=(Path(bundle_dir) if bundle_dir else None))
            _check_identity(report, result_record)
            _check_source_reference(report, result_record)

    if canon == "score-reproduction":
        replay = _check_scorer_replay(report, scorer_argv=scorer_argv,
                                       expected_metrics=expected_metrics,
                                       tolerance=tolerance,
                                       cwd=str(out) if out else None)
        report._scorer_replay = replay  # type: ignore[attr-defined]

    if canon in ("inference-reproduction", "cross-hardware-reproduction"):
        # These require real GPU inference. RUN_GPU=false in CI -> NOT_RUN.
        # Never reported as passed (ok stays False, status='not-run').
        report.mark_not_run(f"{canon} requires real AMD-GPU inference evidence "
                            "(RUN_GPU=false); file via a manual review with the evidence")

    return report


def accumulate(profile: str, **kwargs) -> dict:
    """Run a profile AND every lower rung whose inputs are present.

    Programmatic cumulative proof (Round-2 §4.1): the dependency graph is real,
    not just documented. Returns ``{rung: ConformanceReport}`` for each rung up
    to and including ``profile``. Rungs whose required inputs are absent are
    skipped (not failures).
    """
    target = profile_rank(profile)
    out: dict = {}
    for rung in PROFILE_LADDER[: target + 1]:
        out[rung] = check_profile(rung, **kwargs)
    return out
