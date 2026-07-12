import json
from pathlib import Path
from omnidocbench_amd.schema import validate_artifact, SCHEMA_PATH
from omnidocbench_amd.types import RunSummary, PageStatus, AdapterConfig


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
