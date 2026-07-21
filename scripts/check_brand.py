#!/usr/bin/env python3
"""Brand-residue gate for OmniDocBench-ROCm.

Fails if any forbidden old-brand token appears outside the internal-record
exclusion set. The product/user-facing surface must be clean.

Excluded (internal engineering records that legitimately discuss the rename):
  docs/superpowers/**, docs/audits/**, docs/adr/**, CHANGELOG.md

Exit 0 = clean, 1 = residue found. Intended for CI and local use.
"""
from __future__ import annotations
import sys
from pathlib import Path

FORBIDDEN = (
    "OmniDocBench-AMD",
    "omnidocbench-amd",
    "omnidocbench_amd",
    "AMD Doc Parsing",
    "Model-AMD",
    "omnidocbench-amd-windows",
)

EXCLUDED_DIRS = ("docs/superpowers", "docs/audits", "docs/adr")
# CHANGELOG records the rename; check_brand.py defines the forbidden tokens;
# test_brand_residue.py uses them as detection fixtures; the P1 migration
# playbook cites the old name in its rename patterns / grep examples. All four
# legitimately contain the old brand.
EXCLUDED_FILES = ("CHANGELOG.md", "scripts/check_brand.py",
                  "tests/test_brand_residue.py", "docs/p1-migration-playbook.md")
SKIP_NAMES = {".git", "__pycache__", ".pytest_cache", "dist", "build", ".eggs", ".superpowers"}


def _excluded(rel_posix: str) -> bool:
    if rel_posix in EXCLUDED_FILES:
        return True
    for d in EXCLUDED_DIRS:
        if rel_posix == d or rel_posix.startswith(d + "/"):
            return True
    return False


def find_residue(root: Path | str | None = None) -> list[tuple[str, int, str]]:
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    hits: list[tuple[str, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(root).parts
        if any(p in SKIP_NAMES or p.endswith(".egg-info") for p in parts):
            continue
        rel_posix = path.relative_to(root).as_posix()
        if _excluded(rel_posix):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for tok in FORBIDDEN:
            for i, line in enumerate(text.splitlines(), 1):
                if tok in line:
                    hits.append((rel_posix, i, tok))
    return hits


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else None
    hits = find_residue(root)
    if not hits:
        print("brand-residue: clean")
        return 0
    print("brand-residue: FORBIDDEN old-brand tokens found:")
    for f, i, tok in hits:
        print(f"  {f}:{i}: '{tok}'")
    print("Allowed only in: docs/superpowers/**, docs/audits/**, docs/adr/**, CHANGELOG.md")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
