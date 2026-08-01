"""Immutable comparison-track catalog (Round-2 P0-4, design Option B).

``contracts/tracks.json`` pins the immutable IDENTITY of each comparison track —
the upstream dataset commit, GT manifest sha256, sorted page-set hash, page
count, scorer revision/protocol/metric_set — so results are only compared within
a track whose FULL identity matches.

Design choice (Option B): :func:`tracks.make_track_id` is UNCHANGED — it remains
the human-readable grouping label derived from (benchmark, version, subset,
protocol). The catalog supplies the immutable *content* identity (page-set hash,
GT hash, scorer revision) that a validator enforces separately: a result whose
``page_set_hash`` / ``gt_manifest_sha256`` / ``scorer.revision`` does not match
the catalog — or is ``unknown`` — is barred from head-to-head comparison. This
achieves P0-4's goal (only results with matching, pinned identity share a track)
without a breaking ``track_id`` change (which would churn every shipped card and
spec-lock, a SemVer major bump).

Hashes are computed from the REAL GT manifest (``OmniDocBench.json``):
``gt_manifest_sha256`` over the file bytes; ``page_set_hash`` over the sorted
list of ``page_info.image_path`` ids (order-independent, deterministic).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import tracks

TRACKS_CATALOG_SCHEMA_VERSION = 1

UPSTREAM_REPOSITORY = "opendatalab/OmniDocBench"
# The locked dataset + scorer commit (OmniDocBench repo HEAD used zone-wide).
# Verified real; advanced only via an explicit dataset/scorer version bump.
UPSTREAM_COMMIT = "2b161d010d2e3aff77a0edef359ea3a6411d23cd"
# The scorer ships inside the OmniDocBench repo, so scorer_revision == upstream.
SCORER_REVISION = UPSTREAM_COMMIT
METRIC_SET = "quick_match + cdm"
GT_MANIFEST_NAME = "OmniDocBench.json"

# Where to look for the GT manifest. Override with the OMNIDOCS_GT env var.
GT_SEARCH = (
    Path("/root/datasets/OmniDocBench_data/OmniDocBench.json"),
    Path("/workspace/OmniDocBench_data/OmniDocBench.json"),
)


def find_gt() -> Path | None:
    """Locate the GT manifest, or None if unavailable in this environment.

    An explicit ``OMNIDOCS_GT`` override is AUTHORITATIVE: a set-but-absent path
    means "no GT available here" — it does NOT silently fall through to the
    default search (which could pin an unintended GT). Default search is used
    only when ``OMNODOCS_GT`` is unset.
    """
    env = os.environ.get("OMNIDOCS_GT")
    if env:
        return Path(env) if Path(env).exists() else None
    for p in GT_SEARCH:
        if p.exists():
            return p
    return None


def _sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def page_set_hash(gt_path: Path | str) -> str:
    """sha256 over the sorted list of page ``image_path`` ids in the GT manifest.

    Order-independent and deterministic: pins the exact page SET (which pages),
    distinct from the GT-file hash (which pins the exact GT version). Two runs
    over different page selections produce different hashes.
    """
    data = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    ids = sorted((e.get("page_info") or {}).get("image_path", "")
                 for e in data if isinstance(e, dict))
    return "sha256:" + hashlib.sha256(
        json.dumps(ids, separators=(",", ":")).encode("utf-8")).hexdigest()


def page_count(gt_path: Path | str) -> int:
    data = json.loads(Path(gt_path).read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else 0


def _full_track(gt_path: Path | str) -> dict:
    tid = tracks.make_track_id(benchmark_id="omnidocbench", benchmark_version="v1.6",
                               dataset_subset="full", scorer_protocol="default")
    return {
        "track_id": tid,
        "version": "1",
        "benchmark": {"id": "omnidocbench", "version": "v1.6"},
        "dataset": {
            "subset": "full",
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_commit": UPSTREAM_COMMIT,
            "dataset_revision": UPSTREAM_COMMIT,
            "page_count": page_count(gt_path),
            "gt_manifest": GT_MANIFEST_NAME,
            "gt_manifest_sha256": _sha256_file(Path(gt_path)),
            "page_set_hash": page_set_hash(gt_path),
        },
        "scorer": {"protocol": "default", "revision": SCORER_REVISION, "metric_set": METRIC_SET},
        "eligibility": {
            "excluded_statuses": list(tracks.HIDDEN_STATUS),
            "must_match": ["dataset.page_set_hash", "dataset.gt_manifest_sha256",
                           "scorer.revision"],
        },
    }


def _canary_track(gt_path: Path | str) -> dict:
    tid = tracks.make_track_id(benchmark_id="omnidocbench", benchmark_version="v1.6",
                               dataset_subset="canary", scorer_protocol="default")
    return {
        "track_id": tid,
        "version": "1",
        "benchmark": {"id": "omnidocbench", "version": "v1.6"},
        "dataset": {
            "subset": "canary",
            "upstream_repository": UPSTREAM_REPOSITORY,
            "upstream_commit": UPSTREAM_COMMIT,
            "dataset_revision": UPSTREAM_COMMIT,
            "page_count": None,
            "gt_manifest": GT_MANIFEST_NAME,
            "gt_manifest_sha256": _sha256_file(Path(gt_path)),
            "page_set_hash": "unknown",
        },
        "scorer": {"protocol": "default", "revision": SCORER_REVISION, "metric_set": METRIC_SET},
        "eligibility": {
            "excluded_statuses": list(tracks.HIDDEN_STATUS),
            "must_match": ["dataset.gt_manifest_sha256", "scorer.revision"],
        },
        "note": "canary = quick-smoke subset drawn from the same GT; the exact canary "
                "page selection is not pinned in this catalog (page_set_hash unknown). "
                "Define the canary page list to make results head-to-head comparable "
                "on this track.",
    }


def freeze_tracks(gt_path: Path | str) -> dict:
    """Derive the track catalog from the real GT manifest (deterministic)."""
    return {"schema_version": TRACKS_CATALOG_SCHEMA_VERSION,
            "tracks": [_full_track(gt_path), _canary_track(gt_path)]}
