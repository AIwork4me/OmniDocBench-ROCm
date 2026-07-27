"""rocmdoc.yaml — capability manifest (ADR-0009).

A manifest declares what a model CAN do (platforms/backends/interfaces/licenses)
and under what terms. It is emphatically **not** a benchmark result:

    Manifest  = capability declaration (intent / surface)
    Result    = what was actually measured (evidence)

The load-bearing rule this module enforces is **result alignment**: a published
result_record may NOT claim a platform+backend the manifest does not declare as
supported/experimental. This forbids "faking" a supported platform — a result on
a platform the manifest omits (or marks planned/unsupported) is rejected.

Schema: the ``rocmdoc_manifest`` $def in contracts/artifact-schema.json.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .schema import iter_validation_errors

# Implementation statuses that actually back a published result. "planned" and
# "unsupported" do NOT — a result claiming them is a fake-support violation.
_RESULT_BACKING_STATUSES = {"supported", "experimental"}


def load_manifest(path: Path | str) -> dict:
    """Load a rocmdoc.yaml (or .json) manifest into a dict."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        import json
        return json.loads(text)
    data = yaml.safe_load(text)
    return data or {}


def validate_manifest(manifest: dict) -> list[str]:
    """Return all structural problems with a manifest (empty = valid)."""
    return [f"schema: {m}" for m in iter_validation_errors("rocmdoc_manifest", manifest)]


def declared_capabilities(manifest: dict) -> set[tuple[str, str]]:
    """Return the set of (platform, backend) the manifest declares as result-backing.

    Only implementations with status in {supported, experimental} back a result.
    A backend of "" (any) on a platform declares the whole platform.
    """
    caps: set[tuple[str, str]] = set()
    for impl in manifest.get("implementations") or []:
        if impl.get("status", "supported") not in _RESULT_BACKING_STATUSES:
            continue
        plat = impl.get("platform")
        back = impl.get("backend") or ""
        if plat:
            caps.add((plat, back))
    return caps


def declared_platforms(manifest: dict) -> list[str]:
    """Sorted unique platforms the manifest declares as result-backing."""
    return sorted({plat for plat, _ in declared_capabilities(manifest)})


def check_result_alignment(manifest: dict, card: dict) -> list[str]:
    """Forbid a v2 card's results from claiming unsupported platforms/backends.

    For each result, its (coverage.platform, implementation.backend) must be
    declared by the manifest as result-backing (status supported/experimental). A
    result on a platform the manifest omits or marks planned/unsupported is a
    fake-support violation. Returns the list of problems (empty = aligned).

    A manifest backend of "" (wildcard) matches any result backend on that
    platform, so a manifest need not enumerate every backend variant.
    """
    problems: list[str] = []
    caps = declared_capabilities(manifest)
    plat_backs: dict[str, set[str]] = {}
    wildcard_plats: set[str] = set()
    for plat, back in caps:
        plat_backs.setdefault(plat, set()).add(back)
        if back == "":
            wildcard_plats.add(plat)

    results = card.get("results") if isinstance(card, dict) else card
    for i, res in enumerate(results or []):
        plat = (res.get("coverage") or {}).get("platform")
        back = (res.get("implementation") or {}).get("backend") or ""
        if not plat:
            problems.append(f"results[{i}]: no coverage.platform — cannot align to manifest")
            continue
        if plat not in plat_backs:
            problems.append(
                f"results[{i}]: result claims platform {plat!r} not declared as "
                f"supported/experimental by the manifest (fake-support; ADR-0009)")
            continue
        if plat in wildcard_plats:
            continue  # manifest declared the whole platform (backend "")
        if back and back not in plat_backs[plat]:
            problems.append(
                f"results[{i}]: result claims backend {back!r} on {plat!r} not declared "
                f"by the manifest (declared: {sorted(plat_backs[plat])})")
    return problems


def assert_manifest_aligned(manifest: dict, card: dict) -> None:
    problems = check_result_alignment(manifest, card)
    if problems:
        raise ValueError("manifest/result misalignment:\n  - " + "\n  - ".join(problems))
