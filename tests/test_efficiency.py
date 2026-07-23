import json
from pathlib import Path
from omnidocbench_rocm.types import RunSummary, PageStatus
from omnidocbench_rocm.schema import validate_artifact


def test_runsummary_roundtrips_efficiency(tmp_path):
    eff = {"latency_s_per_page": 1.23, "peak_vram_mb": 38912, "gpu": "gfx1100"}
    rs = RunSummary(count=2, ok=2, fail=0, fallback=0, limit_pages=None,
                    stats=[PageStatus("a.png", "ok", seconds=1.0, attempts=1),
                           PageStatus("b.png", "ok", seconds=1.46, attempts=1)],
                    engine="vllm", efficiency=eff)
    p = tmp_path / "_run_stats.json"
    rs.write(p)
    validate_artifact("run_stats", json.loads(p.read_text()))  # schema accepts efficiency
    back = RunSummary.from_run_stats(p)
    assert back.efficiency == eff


def test_runsummary_omits_efficiency_when_none(tmp_path):
    """Backward-compat: when efficiency is None it must NOT appear in the file."""
    rs = RunSummary(count=1, ok=1, fail=0, fallback=0, limit_pages=None,
                    stats=[PageStatus("a.png", "ok", seconds=1.0, attempts=1)],
                    engine="smoke")
    p = tmp_path / "_run_stats.json"
    rs.write(p)
    obj = json.loads(p.read_text())
    assert "efficiency" not in obj          # smoke runs stay clean
    validate_artifact("run_stats", obj)     # schema still accepts it
    back = RunSummary.from_run_stats(p)
    assert back.efficiency is None


# ── ADR-0003: engine-derived efficiency (stages._derive_efficiency) ──────────
# Pure, GPU-free unit tests for the helper that stage_publish calls after
# reading `engine`. Closes the Task-4 gap where run_summary.efficiency was
# schema-only: the publish -> write_run_summary path must actually populate it.

from omnidocbench_rocm import stages
from omnidocbench_rocm import artifact_utils as au


def test_derive_latency_from_stats():
    run_stats = {"schema_version": 1, "count": 2, "ok": 2, "fail": 0, "fallback": 0,
                 "limit_pages": None, "engine": "vllm",
                 "stats": [{"image": "a.png", "status": "ok", "seconds": 1.0, "attempts": 1},
                           {"image": "b.png", "status": "ok", "seconds": 3.0, "attempts": 1}]}
    eff = stages._derive_efficiency(run_stats)  # mean of ok-page seconds = 2.0
    assert eff["latency_s_per_page"] == 2.0


def test_derive_efficiency_merges_adapter_reported():
    run_stats = {"schema_version": 1, "count": 1, "ok": 1, "fail": 0, "fallback": 0,
                 "limit_pages": None, "engine": "vllm",
                 "stats": [{"image": "a.png", "status": "ok", "seconds": 2.0, "attempts": 1}],
                 "efficiency": {"peak_vram_mb": 38912, "gpu": "gfx1100"}}
    eff = stages._derive_efficiency(run_stats)
    assert eff["latency_s_per_page"] == 2.0
    assert eff["peak_vram_mb"] == 38912 and eff["gpu"] == "gfx1100"


def test_derive_efficiency_empty_when_no_ok_seconds():
    """No ok-page seconds -> empty dict (so write_run_summary omits the key)."""
    run_stats = {"schema_version": 1, "count": 1, "ok": 0, "fail": 1, "fallback": 0,
                 "limit_pages": None, "engine": "smoke",
                 "stats": [{"image": "a.png", "status": "fail", "seconds": 1.0, "attempts": 1}]}
    eff = stages._derive_efficiency(run_stats)
    assert eff == {}


def test_write_run_summary_carries_efficiency_when_truthy(tmp_path):
    """write_run_summary includes `efficiency` only when truthy (backward-compat)."""
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 1, "ok": 1, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": "vllm",
                              "stats": [{"image": "a.png", "status": "ok", "seconds": 2.0,
                                         "attempts": 1}]}))
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps({}))
    dest = tmp_path / "summary.json"
    eff = {"latency_s_per_page": 2.0, "peak_vram_mb": 38912, "gpu": "gfx1100"}
    au.write_run_summary(save_name="s", run_stats_path=rs, metric_result_path=metric,
                         destination=dest, cdm=False, efficiency=eff)
    summary = json.loads(dest.read_text())
    assert summary["efficiency"] == eff
    validate_artifact("run_summary", summary)


def test_write_run_summary_omits_efficiency_when_none(tmp_path):
    """Backward-compat: existing callers passing no efficiency stay clean."""
    rs = tmp_path / "_run_stats.json"
    rs.write_text(json.dumps({"schema_version": 1, "count": 1, "ok": 1, "fail": 0,
                              "fallback": 0, "limit_pages": None, "engine": "smoke",
                              "stats": []}))
    metric = tmp_path / "metric.json"
    metric.write_text(json.dumps({}))
    dest = tmp_path / "summary.json"
    au.write_run_summary(save_name="s", run_stats_path=rs, metric_result_path=metric,
                         destination=dest, cdm=False)   # no efficiency kwarg
    summary = json.loads(dest.read_text())
    assert "efficiency" not in summary
