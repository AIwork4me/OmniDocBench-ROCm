"""Tests for behavioral conformance profiles + fake CLI fixtures (ADR-0011)."""
from pathlib import Path
import pytest
from omnidocbench_rocm.conformance_profiles import (
    check_profile, check_partial_success, PROFILE_ORDER, PROFILES,
)

FX = Path(__file__).parent / "fixtures"
CLI = FX / "fake_cli"
IMG = FX / "cli_images"


def test_profiles_set():
    assert set(PROFILE_ORDER) == PROFILES
    assert PROFILE_ORDER == ("base", "runtime-core", "benchmark-omnidocbench-v16", "reproducible-score")


def test_success_cli_passes_all_cli_profiles(tmp_path):
    for prof in ("base", "runtime-core", "benchmark-omnidocbench-v16"):
        r = check_profile(prof, cli_path=CLI / "success.py", img_dir=IMG, out_dir=tmp_path / prof)
        assert r.ok, f"{prof}: {r.failures}"


def test_fatal_cli_crash_is_detected(tmp_path):
    # A CLI that crashes on parse (exit 5) must fail the benchmark profile (R2 violation).
    r = check_profile("benchmark-omnidocbench-v16", cli_path=CLI / "fatal.py",
                      img_dir=IMG, out_dir=tmp_path / "fatal")
    assert not r.ok
    assert any("exit 0/1, got 5" in f or "crash" in f for f in r.failures)


def test_badjson_cli_fails_json_purity():
    # Non-pure-JSON stdout is a CONTRACT violation; runtime-core must catch it.
    r = check_profile("runtime-core", cli_path=CLI / "badjson.py")
    assert not r.ok
    assert any("not valid JSON" in f or "not pure JSON" in f for f in r.failures)


def test_backend_mismatch_detected(tmp_path):
    # Requested vllm but the fake reports onnx-rocm -> exit 3 -> profile fails.
    r = check_profile("benchmark-omnidocbench-v16", cli_path=CLI / "backend_mismatch.py",
                      img_dir=IMG, out_dir=tmp_path / "bm", requested_backend="vllm")
    assert not r.ok
    assert any("got 3" in f or "mismatch" in f for f in r.failures)


def test_backend_match_passes(tmp_path):
    r = check_profile("benchmark-omnidocbench-v16", cli_path=CLI / "backend_mismatch.py",
                      img_dir=IMG, out_dir=tmp_path / "bmok", requested_backend="onnx-rocm")
    assert r.ok, r.failures


def test_partial_success_does_not_crash(tmp_path):
    # A CLI that fails some pages must continue (status partial, exit 1), not crash.
    r = check_partial_success(CLI / "partial.py", IMG, tmp_path / "partial")
    assert r.ok, r.failures


def test_partial_cli_passes_benchmark_profile(tmp_path):
    # The benchmark profile accepts a partial run (exit 1, status partial).
    r = check_profile("benchmark-omnidocbench-v16", cli_path=CLI / "partial.py",
                      img_dir=IMG, out_dir=tmp_path / "p2")
    assert r.ok, r.failures


def test_reproducible_score_good_record():
    good = {"result_id": "m__linux-rocm__vllm__fp16__v16", "status": "valid",
            "assurance": "evidence-complete",
            "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 95.0},
            "provenance": {"created_at_utc": "2026-07-27T00:00:00Z", "git_commit": "abc"},
            "artifacts": {"run_summary": "rs.json"}}
    r = check_profile("reproducible-score", result_record=good)
    assert r.ok, r.failures


def test_reproducible_score_bad_record():
    bad = {"result_id": "x", "status": "valid", "assurance": "submitted",
           "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 1.0},
           "provenance": {"created_at_utc": "2026/07/27"},  # not RFC3339
           "artifacts": {"foo_sha256": "deadbeef"}}          # bad hash
    r = check_profile("reproducible-score", result_record=bad)
    assert not r.ok
    joined = " ".join(r.failures)
    assert "git_commit" in joined
    assert "RFC3339" in joined
    assert "sha256" in joined


def test_reproducible_score_verifies_real_file_hash(tmp_path):
    f = tmp_path / "metric.json"
    f.write_bytes(b'{"hello": "world"}')
    import hashlib
    digest = "sha256:" + hashlib.sha256(b'{"hello": "world"}').hexdigest()
    rec = {"result_id": "x", "status": "valid", "assurance": "evidence-complete",
           "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 1.0},
           "provenance": {"created_at_utc": "2026-07-27T00:00:00Z", "git_commit": "abc"},
           "artifacts": {"metric_result": str(f), "metric_result_sha256": digest}}
    r = check_profile("reproducible-score", result_record=rec, bundle_dir=tmp_path)
    assert r.ok, r.failures
    # tamper -> fails
    rec["artifacts"]["metric_result_sha256"] = "sha256:" + "0" * 64
    r2 = check_profile("reproducible-score", result_record=rec, bundle_dir=tmp_path)
    assert not r2.ok and any("does not match" in f for f in r2.failures)
