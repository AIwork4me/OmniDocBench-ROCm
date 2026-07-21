import json
from pathlib import Path
from omnidocbench_rocm.schema import validate_artifact, SCHEMA_PATH
from omnidocbench_rocm.types import RunSummary, PageStatus, AdapterConfig


def _run_stats_obj():
    return {
        "schema_version": 1,
        "count": 3, "ok": 2, "fail": 1, "fallback": 0, "limit_pages": None,
        "engine": "smoke",
        "stats": [
            {"image": "a.png", "status": "ok", "error": "", "seconds": 0.1, "attempts": 1},
            {"image": "b.png", "status": "failed: timeout", "error": "timeout", "seconds": 5.0, "attempts": 2},
        ],
    }


def test_run_stats_schema_valid():
    validate_artifact("run_stats", _run_stats_obj())  # no exception


def test_run_stats_rejects_missing_field():
    bad = _run_stats_obj(); del bad["count"]
    try:
        validate_artifact("run_stats", bad)
        assert False, "should have raised"
    except Exception:
        pass


def test_runsummary_roundtrip(tmp_path):
    rs = RunSummary(count=3, ok=2, fail=1, fallback=0, limit_pages=None,
                    stats=[PageStatus("a.png", "ok")], engine="smoke")
    p = tmp_path / "_run_stats.json"
    rs.write(p)
    back = RunSummary.from_run_stats(p)
    assert back.count == 3 and back.ok == 2 and back.fail == 1


def test_model_card_accepts_optional_backend_fields():
    card = {
        "schema_version": 1, "model_id": "x", "model_version": "0.1",
        "platforms": ["linux-rocm"], "badge": {"linux-rocm": "community"},
        "eval_date": "2026-07-19", "omnidocbench_version": "v1.6",
        "overall": None, "hardware": {}, "artifacts": {},
        "backend": "vllm-rocm", "execution_provider": "ROCMExecutionProvider",
        "backend_family": "rocm", "compatibility_status": "first-class",
        "target_backend": "migraphx",
    }
    validate_artifact("model_card", card)  # must not raise


def test_minimal_model_card_still_validates():
    minimal = {
        "schema_version": 1, "model_id": "x", "model_version": "0.1",
        "platforms": ["linux-rocm"], "badge": {"linux-rocm": "community"},
        "eval_date": "2026-07-19", "omnidocbench_version": "v1.6",
        "overall": None, "hardware": {}, "artifacts": {},
    }
    validate_artifact("model_card", minimal)  # optional fields absent -> still valid


def test_provenance_schema_accepts_backend():
    base = {"schema_version": 1, "created_at_utc": "t", "git_commit": "c",
            "platform": "linux-rocm", "engine_version": "0.3.0", "model_id": "m",
            "adapter_command": "python a.py", "dataset_manifest_path": "m.json",
            "dataset_revision": "v1.6", "prediction_dir": "/p", "page_count": 3,
            "ok_pages": 3, "failed_pages": 0, "metric_result_paths": [],
            "run_summary_paths": [], "run_stats_path": "/r.json", "backend": "vllm"}
    validate_artifact("provenance", base)  # has backend -> valid
    bad = dict(base); del bad["backend"]
    try:
        validate_artifact("provenance", bad)
        assert False, "provenance should require backend"
    except Exception:
        pass
