"""Tests for the rocmdoc.yaml manifest + result alignment (ADR-0009)."""
import pytest
from omnidocbench_rocm.manifest import (
    load_manifest, validate_manifest, declared_capabilities, declared_platforms,
    check_result_alignment,
)


def _manifest(platforms):
    impls = []
    for plat, back, status in platforms:
        impls.append({"platform": plat, "backend": back, "status": status,
                      "interface": "adapter-script"})
    return {"schema_version": 1, "project": {"name": "x"}, "upstream": {"name": "u"},
            "model": {"id": "m"}, "licenses": {"code": {"category": "open-source-ai"}},
            "interfaces": ["adapter-script"], "implementations": impls}


def test_validate_manifest_good():
    mf = _manifest([("linux-rocm", "vllm", "supported"), ("windows-hip", "llama-cpp-hip", "planned")])
    assert validate_manifest(mf) == []


def test_declared_capabilities_excludes_non_backing():
    mf = _manifest([("linux-rocm", "vllm", "supported"),
                    ("windows-hip", "llama-cpp-hip", "planned"),
                    ("linux-rocm", "onnx-rocm", "unsupported")])
    caps = declared_capabilities(mf)
    assert ("linux-rocm", "vllm") in caps
    assert ("windows-hip", "llama-cpp-hip") not in caps  # planned doesn't back results
    assert ("linux-rocm", "onnx-rocm") not in caps       # unsupported doesn't either
    assert declared_platforms(mf) == ["linux-rocm"]


def test_alignment_allows_declared_result():
    mf = _manifest([("linux-rocm", "vllm", "supported")])
    card = {"results": [{"coverage": {"platform": "linux-rocm"},
                         "implementation": {"backend": "vllm"}}]}
    assert check_result_alignment(mf, card) == []


def test_alignment_rejects_undeclared_platform():
    mf = _manifest([("linux-rocm", "vllm", "supported")])
    card = {"results": [{"coverage": {"platform": "windows-hip"},  # not declared
                         "implementation": {"backend": "llama-cpp-hip"}}]}
    probs = check_result_alignment(mf, card)
    assert any("not declared" in p and "fake-support" in p for p in probs)


def test_alignment_rejects_declared_but_planned():
    mf = _manifest([("windows-hip", "llama-cpp-hip", "planned")])
    card = {"results": [{"coverage": {"platform": "windows-hip"},
                         "implementation": {"backend": "llama-cpp-hip"}}]}
    probs = check_result_alignment(mf, card)
    assert any("not declared" in p for p in probs)


def test_alignment_wildcard_backend_matches_any():
    mf = _manifest([("linux-rocm", "", "supported")])  # whole platform
    card = {"results": [{"coverage": {"platform": "linux-rocm"},
                         "implementation": {"backend": "anything-at-all"}}]}
    assert check_result_alignment(mf, card) == []


def test_alignment_rejects_undeclared_backend():
    mf = _manifest([("linux-rocm", "vllm", "supported")])
    card = {"results": [{"coverage": {"platform": "linux-rocm"},
                         "implementation": {"backend": "onnx-rocm"}}]}  # not declared
    probs = check_result_alignment(mf, card)
    assert any("backend" in p for p in probs)


def test_example_manifest_loads_and_aligns():
    mf = load_manifest("examples/rocmdoc.example.yaml")
    assert validate_manifest(mf) == []
    # both example-vlm implementations are supported -> results align
    assert declared_platforms(mf) == ["linux-rocm", "windows-hip"]
