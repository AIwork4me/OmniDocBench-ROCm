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
