#!/usr/bin/env python3
"""result_id uniqueness gate (ADR-0007, ADR-0012).

Asserts result_ids are unique across the canonical results store AND every v2
model card found under the repo (so two cards cannot claim the same id, and no
canonical entry collides with a card). Exit 0 = clean, 1 = duplicate found.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _collect() -> list[tuple[str, str]]:
    """Return [(result_id, source_path), ...] from canonical + all *.json v2 cards."""
    out: list[tuple[str, str]] = []
    canon = _REPO / "hub" / "canonical_results.json"
    if canon.exists():
        data = json.loads(canon.read_text(encoding="utf-8"))
        rows = data["results"] if isinstance(data, dict) else data
        for r in rows:
            out.append((r.get("result_id", ""), f"{canon.name}:{r.get('model_id')}"))
    # scan examples/ + tests/fixtures/ for v2 cards
    for base in (_REPO / "examples", _REPO / "tests" / "fixtures"):
        if not base.exists():
            continue
        for p in base.rglob("*.json"):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("schema_version") == 2:
                for r in obj.get("results", []):
                    out.append((r.get("result_id", ""), str(p.relative_to(_REPO))))
    return out


def main(argv: list[str]) -> int:
    pairs = _collect()
    seen: dict[str, str] = {}
    dups: list[str] = []
    for rid, src in pairs:
        if not rid:
            continue
        if rid in seen:
            dups.append(f"{rid!r}: {src} duplicates {seen[rid]}")
        else:
            seen[rid] = src
    if not dups:
        print(f"result_ids: {len(pairs)} ids, all unique ✓"); return 0
    print("result_ids: DUPLICATES")
    for d in dups:
        print(" -", d)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
