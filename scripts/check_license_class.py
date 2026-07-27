#!/usr/bin/env python3
"""License-classification gate (ADR-0010).

Asserts every registry + canonical-results entry carries a valid
``license_category``, and that a declared category for a KNOWN license agrees
with the engine's classifier (catches a hand-set category that contradicts the
license). Exit 0 = clean, 1 = violation. Intended for CI.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "engine"))

from omnidocbench_rocm.license_class import LICENSE_CATEGORIES, classify  # noqa: E402


def _check_registry(path: Path) -> list[str]:
    rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    problems: list[str] = []
    for i, r in enumerate(rows):
        ctx = f"registry entry#{i} ({r.get('model_id', '?')})"
        cat = r.get("license_category")
        if cat is None:
            problems.append(f"{ctx}: missing license_category (set one; never default to open-source-ai)")
        elif cat not in LICENSE_CATEGORIES:
            problems.append(f"{ctx}: bad license_category {cat!r}")
        # cross-check: a known license must classify consistently
        lic = r.get("license") or ""
        known = classify(lic)
        if lic and known != "unknown" and known != cat:
            problems.append(f"{ctx}: license_category {cat!r} disagrees with classifier ({known!r}) for {lic!r}")
    return problems


def _check_canonical(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["results"] if isinstance(data, dict) else data
    problems: list[str] = []
    for i, r in enumerate(rows):
        ctx = f"canonical_results[{i}] ({r.get('model_id', '?')})"
        cat = r.get("license_category")
        if cat is None:
            problems.append(f"{ctx}: missing license_category")
        elif cat not in LICENSE_CATEGORIES:
            problems.append(f"{ctx}: bad license_category {cat!r}")
    return problems


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="License-classification gate.")
    ap.add_argument("--registry", default="hub/registry.yaml")
    ap.add_argument("--canonical", default="hub/canonical_results.json")
    a = ap.parse_args(argv)
    problems = _check_registry(Path(a.registry)) + _check_canonical(Path(a.canonical))
    if not problems:
        print("license-classification: clean ✓"); return 0
    print("license-classification: INVALID")
    for p in problems:
        print(" -", p)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
