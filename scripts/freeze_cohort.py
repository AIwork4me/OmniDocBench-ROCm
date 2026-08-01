#!/usr/bin/env python3
"""Freeze (or refresh) contracts/cohort.json — the central contract cohort manifest.

Derives every field from the real shipped contract commit on the default branch;
no hand-editing, no fabricated SHA. Run after any contract change that lands on
the default branch (the lock then advances to the new contract commit).
Idempotent: re-running with an unchanged contract reproduces the same bytes.

The manifest is the authoritative cohort statement that model-repo spec-locks
are validated against (Round-2 P0-2).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "engine"))

from omnidocbench_rocm.cohort import freeze_cohort  # noqa: E402


def main() -> int:
    doc = freeze_cohort(REPO)
    out = REPO / "contracts" / "cohort.json"
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[freeze] cohort manifest -> {out.relative_to(REPO)} "
          f"(central_commit {doc['central_commit'][:7]}, {doc['contract_release']}, "
          f"schema sha256 {doc['artifact_schema']['sha256'][:7]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
