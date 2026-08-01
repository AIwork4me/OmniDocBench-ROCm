"""Regression guard for the central canonical store + registry (Phase-0 detectors).

These load the REAL ``hub/canonical_results.json`` + ``hub/registry.yaml`` +
imports and assert the store is free of the known defect classes. Each test names
one class and fails with the offending ids until the data is corrected.

Detectors-first: after the detectors land these go RED (documenting the defects);
the Phase-0 data fixes then turn them GREEN. They stay green thereafter as
regression guards — any future regression of the same class fails CI here.
"""
import json
from pathlib import Path

import yaml

from omnidocbench_rocm import hub

REPO = Path(__file__).resolve().parents[1]
HUB = REPO / "hub"
CANONICAL = HUB / "canonical_results.json"
REGISTRY = HUB / "registry.yaml"


def _real_findings():
    rows = hub.load_canonical(CANONICAL)
    imports = hub.load_imports_store(HUB)
    registry_rows = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else None
    return hub.check_drift(canonical_rows=rows, imports=imports, registry_rows=registry_rows)


def test_no_pipeline_backend_under_vlm_model_id():
    """ADR-0017: a composite pipeline must be its own model_id, not filed under a
    VLM model_id (e.g. mineru2.5 must not carry 86.x pipeline scores)."""
    bad = [f for f in _real_findings() if f["kind"] == "pipeline-and-vlm-same-model-id"]
    assert not bad, "pipeline results filed under a VLM model_id: " + json.dumps(bad, ensure_ascii=False)


def test_no_canary_track_result_marked_valid():
    """A canary/sample-track result (e.g. the 150-page canary) must not be
    leaderboard-valid."""
    bad = [f for f in _real_findings() if f["kind"] == "canary-track-result-valid"]
    assert not bad, "canary/sample-track result is leaderboard-valid: " + json.dumps(bad, ensure_ascii=False)


def test_no_license_category_drift():
    """A model's license_category must agree between registry and its VALID
    canonical rows (one label per model, not open-source-ai vs open-weights)."""
    bad = [f for f in _real_findings() if f["kind"] == "license-category-drift"]
    assert not bad, "license_category drifts between registry and canonical: " + json.dumps(bad, ensure_ascii=False)
