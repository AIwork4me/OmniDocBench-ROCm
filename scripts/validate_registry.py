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


def validate_against_model_card(rows: list[dict], model_card: dict,
                                model_id: str, platform: str) -> list[str]:
    """Cross-check one registry row against a model card.

    Asserts the registry row exists for ``model_id`` on ``platform``, and that
    its Overall (2 dp) and badge match the model card. Returns a list of error
    strings (empty = consistent).
    """
    import json as _json
    errors: list[str] = []
    if isinstance(model_card, (str, Path)):
        model_card = _json.loads(Path(model_card).read_text(encoding="utf-8"))
    row = next((r for r in rows if isinstance(r, dict) and r.get("model_id") == model_id), None)
    if row is None:
        return [f"registry has no row for model_id {model_id!r}"]
    entry = (row.get("platforms") or {}).get(platform)
    if not isinstance(entry, dict):
        return [f"registry has no {platform} entry for {model_id!r}"]
    mc_overall = model_card.get("overall")
    reg_overall = entry.get("overall")
    if mc_overall is not None and reg_overall is not None and \
            round(float(reg_overall), 2) != round(float(mc_overall), 2):
        errors.append(f"{model_id}/{platform}: registry overall {reg_overall} != "
                      f"model_card overall {mc_overall}")
    reg_badge = entry.get("badge")
    mc_badge = (model_card.get("badge") or {}).get(platform)
    if mc_badge is not None and reg_badge is not None and reg_badge != mc_badge:
        errors.append(f"{model_id}/{platform}: registry badge {reg_badge!r} != "
                      f"model_card badge {mc_badge!r}")
    return errors


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Validate hub/registry.yaml structure (+ optional model-card cross-check).")
    ap.add_argument("path", nargs="?", default="hub/registry.yaml")
    ap.add_argument("--model-card", default="",
                    help="model_card.json to cross-check Overall/badge against")
    ap.add_argument("--model-id", default="", help="model_id for the cross-check")
    ap.add_argument("--platform", default="linux-rocm", help="platform for the cross-check")
    a = ap.parse_args(argv)
    rows = yaml.safe_load(Path(a.path).read_text(encoding="utf-8")) or []
    errors = validate_registry(rows)
    if a.model_card:
        if not a.model_id:
            errors.append("--model-card requires --model-id")
        else:
            import json as _json
            mc = _json.loads(Path(a.model_card).read_text(encoding="utf-8"))
            errors.extend(validate_against_model_card(rows, mc, a.model_id, a.platform))
    if not errors:
        label = f"valid ({len(rows)} models)" + (" + model-card cross-check OK" if a.model_card else "")
        print(f"registry: {label}"); return 0
    print("registry: INVALID")
    for e in errors:
        print(" -", e)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
