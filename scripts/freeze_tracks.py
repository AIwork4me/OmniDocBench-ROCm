#!/usr/bin/env python3
"""Freeze (or refresh) contracts/tracks.json — the immutable comparison-track catalog.

Computes the real GT manifest sha256 + sorted page-set hash + page count from the
OmniDocBench.json GT manifest, and pins the upstream dataset/scorer commit per
track (Round-2 P0-4, Option B). Requires the GT manifest on disk (set OMNIDOCS_GT
or place it at a known path); refuses to fabricate hashes. Idempotent: re-running
on the same GT reproduces the same bytes.

make_track_id is NOT changed by this script — the catalog supplies the immutable
content identity alongside the existing grouping track_id.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "engine"))

from omnidocbench_rocm.track_catalog import find_gt, freeze_tracks  # noqa: E402


def main() -> int:
    gt = find_gt()
    if gt is None:
        print("[freeze] FATAL: GT manifest (OmniDocBench.json) not found. "
              "Set OMNIDOCS_GT=<path> or place it under /root/datasets/OmniDocBench_data/. "
              "Refusing to fabricate hashes.", file=sys.stderr)
        return 2
    doc = freeze_tracks(gt)
    out = REPO / "contracts" / "tracks.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    full = doc["tracks"][0]
    print(f"[freeze] tracks catalog -> {out.relative_to(REPO)} "
          f"(full {full['track_id']}, pages {full['dataset']['page_count']}, "
          f"page_set_hash {full['dataset']['page_set_hash'][:7]}, "
          f"gt_manifest {full['dataset']['gt_manifest_sha256'][:7]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
