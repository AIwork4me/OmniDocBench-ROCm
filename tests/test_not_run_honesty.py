"""NOT_RUN honesty guard (Round-2 §4 / §15 / Standard §15).

A conformance profile that could not execute (no GPU, RUN_GPU=false, ...) is
NOT_RUN — never reported as passed. This pins that invariant so a future change
cannot silently coerce not-run into a pass. The status-mapping code already
preserves this (``ConformanceReport.mark_not_run`` keeps ``ok=False``); this test
makes that contract explicit and fails if it ever regresses.
"""
from omnidocbench_rocm.conformance import ConformanceReport


def test_mark_not_run_is_never_a_pass():
    r = ConformanceReport()
    assert r.ok is True  # default: a fresh report with no failures
    r.mark_not_run("no GPU in this environment")
    assert r.status == "not-run"
    assert r.ok is False, "a NOT_RUN profile must never be reported as passed (ok must stay False)"
    assert any("NOT_RUN" in note for note in r.failures)
