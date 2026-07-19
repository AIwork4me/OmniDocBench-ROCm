#!/usr/bin/env python3
"""Validate hub/registry.yaml structure for the OmniDocBench-ROCm registry.

Checks each entry: model_id present; repo well-formed owner/name; platform
keys valid; badge enum; overall type (number|null); no duplicate model_id;
no missing platform data. Exit 0 = valid, 1 = invalid.
"""
from __future__ import annotations
import sys
from pathlib import Path
import yaml

PLATFORMS = {"linux-rocm", "windows-hip"}
BADGES = {"verified", "community", "community-wanted"}


def validate_registry(rows: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for i, r in enumerate(rows):
        ctx = f"entry#{i}"
        if not isinstance(r, dict):
            errors.append(f"{ctx}: not a mapping"); continue
        mid = r.get("model_id")
        if not mid or not isinstance(mid, str):
            errors.append(f"{ctx}: missing model_id")
        elif mid in seen:
            errors.append(f"{ctx}: duplicate model_id '{mid}'")
        else:
            seen.add(mid)
        repo = r.get("repo")
        if not isinstance(repo, str) or repo.count("/") != 1 or any(c.isspace() for c in repo):
            errors.append(f"{ctx}: illegal repo '{repo}' (expected owner/name)")
        plats = r.get("platforms")
        if not isinstance(plats, dict) or not plats:
            errors.append(f"{ctx}: missing platforms data"); continue
        for k, v in plats.items():
            if k not in PLATFORMS:
                errors.append(f"{ctx}: unknown platform key '{k}'"); continue
            if not isinstance(v, dict):
                errors.append(f"{ctx}.{k}: not a mapping"); continue
            if v.get("badge") not in BADGES:
                errors.append(f"{ctx}.{k}: bad badge '{v.get('badge')}'")
            overall = v.get("overall")
            if overall is not None and not isinstance(overall, (int, float)):
                errors.append(f"{ctx}.{k}: overall must be number or null")
    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else Path("hub/registry.yaml")
    rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    errors = validate_registry(rows)
    if not errors:
        print(f"registry: valid ({len(rows)} models)"); return 0
    print("registry: INVALID")
    for e in errors:
        print(" -", e)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
