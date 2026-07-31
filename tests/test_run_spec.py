"""Identity v3 — run_spec / run_spec_hash / result_id (Round-2 ADR-0015, §13 7-10)."""
import pytest
from omnidocbench_rocm import run_spec as rs


def _spec(**over):
    base = rs.build_run_spec(
        model={"model_id": "ovisocr2", "model_revision": "r1"},
        implementation={"implementation_id": "ovisocr2-vllm-embedded", "platform": "linux-rocm",
                        "backend": "vllm", "precision": "bf16"},
        benchmark={"benchmark_id": "omnidocbench", "benchmark_version": "v1.6",
                   "dataset_subset": "full", "scorer_revision": "2b161d0"},
        inference={"prompt_hash": "sha256:" + "c" * 64})
    for k, v in over.items():
        base["implementation"][k] = v
    return base


def test_run_spec_hash_is_deterministic():
    assert rs.run_spec_hash(_spec()) == rs.run_spec_hash(_spec())


def test_result_id_v3_deterministic():
    a = rs.make_result_id_v3("ovisocr2", "omnidocbench", _spec())
    b = rs.make_result_id_v3("ovisocr2", "omnidocbench", _spec())
    assert a == b and a.startswith("ovisocr2-omnidocbench-")


def test_material_change_yields_new_identity():
    base = rs.make_result_id_v3("ovisocr2", "omnidocbench", _spec())
    # prompt change (inference)
    other = _spec()
    other["inference"]["prompt_hash"] = "sha256:" + "d" * 64
    assert rs.make_result_id_v3("ovisocr2", "omnidocbench", other) != base
    # precision change (implementation)
    other2 = _spec(precision="fp16")
    assert rs.make_result_id_v3("ovisocr2", "omnidocbench", other2) != base
    # scorer revision change (benchmark)
    other3 = _spec()
    other3["benchmark"]["scorer_revision"] = "deadbee"
    assert rs.make_result_id_v3("ovisocr2", "omnidocbench", other3) != base


def test_identity_change_on_weights_revision():
    a = rs.make_result_id_v3("m", "omnidocbench", _spec())
    s = _spec(); s["model"]["weights_revision"] = "v2"
    assert rs.make_result_id_v3("m", "omnidocbench", s) != a


def test_default_sentinel_is_flagged():
    spec = rs.build_run_spec(
        model={"model_id": "x"},
        implementation={"platform": "linux-rocm", "backend": "default", "precision": "default"},
        benchmark={"benchmark_id": "omnidocbench", "benchmark_version": "v1.6"})
    assert set(rs.uses_default_sentinel(spec)) == {"implementation.backend",
                                                    "implementation.precision"}


def test_unknown_must_be_explicit_not_default():
    spec = rs.build_run_spec(
        model={"model_id": "x"},
        implementation={"implementation_id": "x-vllm", "platform": "linux-rocm",
                        "backend": "unknown", "precision": "unknown"},
        benchmark={"benchmark_id": "omnidocbench", "benchmark_version": "v1.6"})
    # unknown is allowed (not the forbidden default), but flags insufficient identity
    assert rs.uses_default_sentinel(spec) == []
    assert rs.insufficient_identity(spec)  # backend/precision unknown -> not in default table


def test_missing_critical_fields_detected():
    spec = rs.build_run_spec(model={}, implementation={}, benchmark={}, inference={})
    assert "implementation.backend" in rs.missing_critical(spec)


def test_canonical_json_sorts_keys():
    a = rs.canonical_json({"b": 1, "a": {"y": 2, "x": 1}})
    b = rs.canonical_json({"a": {"x": 1, "y": 2}, "b": 1})
    assert a == b


def test_run_spec_hash_full_sha256():
    h = rs.run_spec_hash(_spec())
    assert h.startswith("sha256:") and len(h) == len("sha256:") + 64
