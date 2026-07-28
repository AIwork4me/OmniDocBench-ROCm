"""Round-2 conformance profile semantics (ADR-0018, §13 18-24)."""
import sys
from pathlib import Path
import pytest
from omnidocbench_rocm import conformance_profiles as cp
from omnidocbench_rocm.conformance_profiles import (
    PROFILE_ORDER, PROFILES, PROFILE_LADDER, ALL_PROFILES, check_profile, accumulate,
    profile_includes, assert_no_network,
)

FX = Path(__file__).parent / "fixtures"
CLI = FX / "fake_cli"
IMG = FX / "cli_images"


def test_v2_names_preserved_unchanged():
    # back-compat invariant the v2 test relies on
    assert set(PROFILE_ORDER) == PROFILES
    assert "runtime-core" in ALL_PROFILES and "runtime-contract" in ALL_PROFILES


def test_aliases_resolve_to_canonical():
    assert cp._resolve("runtime-core") == "runtime-contract"
    assert cp._resolve("benchmark-omnidocbench-v16") == "benchmark-contract"
    assert cp._resolve("reproducible-score") == "evidence-integrity"
    assert cp._resolve("base") == "base"


def test_programmatic_accumulation_graph():
    assert profile_includes("base", "evidence-integrity")
    assert profile_includes("runtime-contract", "score-reproduction")
    assert profile_includes("benchmark-contract", "inference-reproduction")
    assert not profile_includes("score-reproduction", "base")  # not the other way


def test_runtime_contract_alias_matches_v2_behavior(tmp_path):
    r_old = check_profile("runtime-core", cli_path=CLI / "success.py")
    r_new = check_profile("runtime-contract", cli_path=CLI / "success.py")
    assert r_old.ok == r_new.ok is True


def test_reproducible_score_alias_is_evidence_integrity():
    good = {"result_id": "m__linux-rocm__vllm__fp16__v16", "status": "valid",
            "assurance": "evidence-complete",
            "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 95.0},
            "provenance": {"created_at_utc": "2026-07-27T00:00:00Z", "git_commit": "abc"},
            "artifacts": {"run_summary": "rs.json"}}
    assert check_profile("reproducible-score", result_record=good).ok
    assert check_profile("evidence-integrity", result_record=good).ok


def test_evidence_integrity_flags_default_backend_and_bad_run_spec_hash():
    rec = {"result_id": "x", "status": "valid", "assurance": "evidence-complete",
           "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 1.0},
           "provenance": {"created_at_utc": "2026-07-27T00:00:00Z", "git_commit": "abc"},
           "artifacts": {"run_summary": "rs.json"},
           "run_spec": {"implementation": {"backend": "default", "precision": "default"}},
           "run_spec_hash": "sha256:" + "0" * 64}
    r = check_profile("evidence-integrity", result_record=rec)
    joined = " ".join(r.failures)
    assert "default" in joined
    assert "run_spec_hash" in joined or "missing critical" in joined


def test_score_reproduction_actually_runs_scorer(tmp_path):
    argv = [sys.executable, str(FX / "fake_scorer.py"), "--predictions-dir", str(tmp_path),
            "--overall", "95.0"]
    r = check_profile("score-reproduction", scorer_argv=argv,
                      expected_metrics={"overall": 95.0})
    assert r.ok, r.failures


def test_score_reproduction_detects_metric_drift(tmp_path):
    argv = [sys.executable, str(FX / "fake_scorer.py"), "--predictions-dir", str(tmp_path),
            "--overall", "95.0"]
    r = check_profile("score-reproduction", scorer_argv=argv,
                      expected_metrics={"overall": 99.0})
    assert not r.ok and any("did not reproduce" in f for f in r.failures)


def test_score_reproduction_not_run_without_inputs():
    r = check_profile("score-reproduction")
    assert r.status == "not-run" and not r.ok


def test_inference_reproduction_is_not_run_not_passed():
    r = check_profile("inference-reproduction")
    assert r.status == "not-run"
    assert not r.ok  # never reported as passed
    assert any("NOT_RUN" in f for f in r.failures)


def test_cross_hardware_reproduction_is_not_run():
    assert check_profile("cross-hardware-reproduction").status == "not-run"


def test_accumulate_runs_lower_rungs(tmp_path):
    argv = [sys.executable, str(FX / "fake_scorer.py"), "--predictions-dir", str(tmp_path),
            "--overall", "95.0"]
    chain = accumulate("score-reproduction", scorer_argv=argv,
                       expected_metrics={"overall": 95.0})
    assert "evidence-integrity" in chain and "score-reproduction" in chain
    assert chain["score-reproduction"].ok


def test_offline_network_block_really_blocks():
    import socket as _sock
    violated = []

    def _try_connect():
        s = _sock.socket()
        try:
            s.connect(("8.8.8.8", 53))
            return False  # connected = no block
        except OSError:
            violated.append(True)
            return True
        finally:
            s.close()
    assert_no_network(_try_connect)
    assert violated
