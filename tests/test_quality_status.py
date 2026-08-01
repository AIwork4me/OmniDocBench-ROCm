"""QUALITY_STATUS: deterministic (no wall clock), drift-guarded, content from facts."""
from pathlib import Path

from omnidocbench_rocm import quality_status as qs

REPO = Path(__file__).resolve().parents[1]
TARGET = REPO / "QUALITY_STATUS.md"


def test_present_and_in_sync():
    assert TARGET.exists(), "QUALITY_STATUS.md missing — run scripts/render_quality_status.py"
    assert qs.check_quality_status(REPO) == [], qs.check_quality_status(REPO)


def test_deterministic_and_byte_stable():
    a = qs.render_quality_status(REPO)
    b = qs.render_quality_status(REPO)
    assert a == b, "render_quality_status is not byte-stable (non-deterministic input leaked in)"
    # must not embed a moving wall-clock timestamp or a "rendered now" phrase
    assert "Generated at" not in a
    assert "rendered_at" not in a.lower()
    assert "DO NOT EDIT" in a  # generated-artifact marker


def test_content_derived_from_facts():
    txt = qs.render_quality_status(REPO)
    assert "## Cohort" in txt and "rocmdoc-1.0" in txt
    assert "## Comparison tracks" in txt
    assert "omnidocbench-v1-6-full-default" in txt  # from tracks.json
    assert "## Hub / canonical store" in txt and "check_drift findings" in txt
    # the honest live drift findings are surfaced (not hidden)
    assert "unknown-identity-assurance-ceiling" in txt
    assert "multiple-primaries-per-track" in txt
    assert "NOT_RUN" in txt  # GPU honesty


def test_check_reports_staleness_when_file_diverges(tmp_path, monkeypatch):
    # point the renderer at a copy with a stale QUALITY_STATUS to prove --check bites
    import shutil
    for sub in ("contracts", "hub"):
        shutil.copytree(REPO / sub, tmp_path / sub)
    # write a deliberately stale QUALITY_STATUS
    (tmp_path / "QUALITY_STATUS.md").write_text("STALE", encoding="utf-8")
    problems = qs.check_quality_status(tmp_path)
    assert problems and any("stale" in p for p in problems)
