"""Tests for Model Card v2 helpers (ADR-0007)."""
import pytest
from omnidocbench_rocm.model_card_v2 import (
    make_result_id, derive_platforms, result_id_duplicates, validate_card_v2,
    normalize_card_v2, result_tuple,
)


def test_result_id_reproducible_and_unique():
    a = make_result_id(model_id="m", platform="linux-rocm", backend="vllm", precision="fp16", benchmark_version="v1.6")
    b = make_result_id(model_id="m", platform="linux-rocm", backend="vllm", precision="fp16", benchmark_version="v1.6")
    assert a == b  # same tuple -> same id (reproducible)
    # different precision -> different id
    c = make_result_id(model_id="m", platform="linux-rocm", backend="vllm", precision="bf16", benchmark_version="v1.6")
    assert c != a
    # different platform -> different id
    d = make_result_id(model_id="m", platform="windows-hip", backend="vllm", precision="fp16", benchmark_version="v1.6")
    assert d != a
    assert a.endswith(a.split("__")[-1])  # 12-hex suffix present
    assert len(a.split("__")[-1]) == 12


def test_derive_platforms_from_results():
    results = [
        {"coverage": {"platform": "windows-hip"}},
        {"coverage": {"platform": "linux-rocm"}},
        {"coverage": {"platform": "linux-rocm"}},  # dup
    ]
    assert derive_platforms(results) == ["linux-rocm", "windows-hip"]
    assert derive_platforms([]) == []


def test_validate_card_v2_good():
    rid = make_result_id(model_id="m", platform="linux-rocm", backend="vllm", benchmark_version="v1.6")
    card = {"schema_version": 2, "model_id": "m",
            "results": [{"result_id": rid, "status": "valid", "assurance": "evidence-complete",
                         "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
                         "metrics": {"overall": 95.0},
                         "provenance": {"created_at_utc": "2026-07-27T00:00:00Z", "git_commit": "abc"}}]}
    assert validate_card_v2(card) == []


def test_validate_card_v2_platforms_mismatch():
    rid = make_result_id(model_id="m", platform="linux-rocm", benchmark_version="v1.6")
    card = {"schema_version": 2, "model_id": "m", "platforms": ["windows-hip"],  # wrong
            "results": [{"result_id": rid, "status": "valid", "assurance": "submitted",
                         "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
                         "metrics": {"overall": 1.0}, "provenance": {}}]}
    probs = validate_card_v2(card)
    assert any("platforms" in p and "derived" in p for p in probs)


def test_validate_card_v2_duplicate_result_id():
    rid = make_result_id(model_id="m", platform="linux-rocm", benchmark_version="v1.6")
    card = {"schema_version": 2, "model_id": "m", "results": [
        {"result_id": rid, "status": "valid", "assurance": "submitted",
         "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 1.0}, "provenance": {}},
        {"result_id": rid, "status": "valid", "assurance": "submitted",
         "benchmark": {"name": "OmniDocBench", "version": "v1.6"}, "metrics": {"overall": 2.0}, "provenance": {}},
    ]}
    probs = validate_card_v2(card)
    assert any("duplicate result_id" in p for p in probs)


def test_validate_card_v2_primary_must_resolve():
    rid = make_result_id(model_id="m", platform="linux-rocm", benchmark_version="v1.6")
    card = {"schema_version": 2, "model_id": "m", "primary_result_id": "does-not-exist",
            "results": [{"result_id": rid, "status": "valid", "assurance": "submitted",
                         "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
                         "metrics": {"overall": 1.0}, "provenance": {}}]}
    probs = validate_card_v2(card)
    assert any("primary_result_id" in p for p in probs)


def test_validate_card_v2_rejects_model_wide_assurance():
    rid = make_result_id(model_id="m", platform="linux-rocm", benchmark_version="v1.6")
    card = {"schema_version": 2, "model_id": "m", "assurance": "verified",  # propagation anti-pattern
            "results": [{"result_id": rid, "status": "valid", "assurance": "submitted",
                         "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
                         "metrics": {"overall": 1.0}, "provenance": {}}]}
    probs = validate_card_v2(card)
    assert any("propagation" in p for p in probs)


def test_normalize_is_deterministic():
    rid = make_result_id(model_id="m", platform="linux-rocm", benchmark_version="v1.6")
    card = {"schema_version": 2, "model_id": "m", "results": [
        {"result_id": rid, "status": "valid", "assurance": "submitted",
         "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
         "coverage": {"platform": "linux-rocm"},
         "metrics": {"overall": 1.0}, "provenance": {}}]}
    n1 = normalize_card_v2(card)
    n2 = normalize_card_v2(n1)
    assert n1 == n2  # idempotent
    assert n1["platforms"] == ["linux-rocm"]
