#!/usr/bin/env python3
"""Tolerance check for a VERIFIED.yaml (the `verified` badge gate).

Asserts |reproduced_overall - committed_overall| <= tolerance (default 0.5).
Exit 0 = passes, 1 = fails. Part of the verified-reproduction path.
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml


def check_verified(verified: dict, tolerance: float | None = None) -> tuple[bool, str]:
    rep = verified.get("reproduced_overall")
    com = verified.get("committed_overall")
    if rep is None or com is None:
        return False, "missing reproduced_overall or committed_overall"
    tol = tolerance if tolerance is not None else float(verified.get("tolerance", 0.5))
    delta = abs(float(rep) - float(com))
    if delta <= tol:
        return True, f"within tolerance: |{rep} - {com}| = {delta:.3f} <= {tol}"
    return False, f"OUT of tolerance: |{rep} - {com}| = {delta:.3f} > {tol}"


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("VERIFIED.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ok, msg = check_verified(data)
    print(f"VERIFIED {'PASS' if ok else 'FAIL'}: {msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
