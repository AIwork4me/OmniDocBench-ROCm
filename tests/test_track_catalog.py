"""Track catalog: well-formed + (when the GT is present) fresh-freeze drift.

contracts/tracks.json pins the immutable identity of each comparison track
(Round-2 P0-4, Option B). make_track_id is unchanged; the catalog supplies the
content identity a validator enforces. These tests guard structure always, and
re-derive the real hashes from the GT when it is available in the environment
(skipped honestly elsewhere — hashes are never fabricated).
"""
import json
from pathlib import Path

import pytest

from omnidocbench_rocm import track_catalog as tc
from omnidocbench_rocm import tracks

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "contracts" / "tracks.json"


def _full_tid():
    return tracks.make_track_id(benchmark_id="omnidocbench", benchmark_version="v1.6",
                                dataset_subset="full", scorer_protocol="default")


def _canary_tid():
    return tracks.make_track_id(benchmark_id="omnidocbench", benchmark_version="v1.6",
                                dataset_subset="canary", scorer_protocol="default")


def test_catalog_present_and_well_formed():
    assert MANIFEST.exists(), "contracts/tracks.json missing — run scripts/freeze_tracks.py"
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert doc["schema_version"] == tc.TRACKS_CATALOG_SCHEMA_VERSION
    by_subset = {t["dataset"]["subset"]: t for t in doc["tracks"]}
    assert set(by_subset) == {"full", "canary"}

    full = by_subset["full"]
    assert full["track_id"] == _full_tid()
    assert full["benchmark"] == {"id": "omnidocbench", "version": "v1.6"}
    assert full["dataset"]["page_count"] == 1651
    assert full["dataset"]["upstream_commit"] == tc.UPSTREAM_COMMIT
    assert full["dataset"]["dataset_revision"] == tc.UPSTREAM_COMMIT
    assert full["dataset"]["gt_manifest_sha256"].startswith("sha256:") \
        and len(full["dataset"]["gt_manifest_sha256"]) == 7 + 64
    assert full["dataset"]["page_set_hash"].startswith("sha256:") \
        and len(full["dataset"]["page_set_hash"]) == 7 + 64
    assert full["scorer"]["revision"] == tc.SCORER_REVISION
    assert full["scorer"]["metric_set"] == tc.METRIC_SET
    assert "dataset.page_set_hash" in full["eligibility"]["must_match"]
    assert "dataset.gt_manifest_sha256" in full["eligibility"]["must_match"]

    canary = by_subset["canary"]
    assert canary["track_id"] == _canary_tid()
    # canary page selection is honestly NOT pinned here
    assert canary["dataset"]["page_set_hash"] == "unknown"
    assert canary["dataset"]["page_count"] is None


def test_full_track_id_matches_results_in_canonical_store():
    """The catalog's full track_id must equal what the shipped results carry."""
    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    full_tid = next(t["track_id"] for t in doc["tracks"] if t["dataset"]["subset"] == "full")
    canon = json.loads((REPO / "hub" / "canonical_results.json").read_text(encoding="utf-8"))
    carried = {r.get("comparison_track_id") for r in canon["results"]}
    assert full_tid in carried, "catalog full track_id is not used by any shipped result"


def test_catalog_matches_fresh_freeze_when_gt_present():
    """If the GT manifest is available, the committed catalog must equal a fresh freeze."""
    gt = tc.find_gt()
    if gt is None:
        pytest.skip("GT manifest not present in this env; skipping real-hash drift recompute")
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert committed == tc.freeze_tracks(gt)
