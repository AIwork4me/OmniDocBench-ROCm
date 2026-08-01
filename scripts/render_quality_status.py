#!/usr/bin/env python3
"""Render (or --check) QUALITY_STATUS.md — the deterministic central dashboard.

Renders from facts (cohort, tracks, canonical store, drift); deterministic (no
wall clock). With ``--check`` it fails non-zero if the committed file is stale,
so CI catches a forgotten regeneration. DO NOT hand-edit QUALITY_STATUS.md.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "engine"))

from omnidocbench_rocm.quality_status import check_quality_status, render_quality_status  # noqa: E402


def main() -> int:
    if "--check" in sys.argv:
        problems = check_quality_status(REPO)
        if problems:
            for p in problems:
                print(f"QUALITY_STATUS drift: {p}", file=sys.stderr)
            return 1
        print("QUALITY_STATUS.md up to date ✓")
        return 0
    out = REPO / "QUALITY_STATUS.md"
    out.write_text(render_quality_status(REPO), encoding="utf-8")
    print(f"[render] QUALITY_STATUS.md -> {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
