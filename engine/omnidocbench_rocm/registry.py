"""Hub model registry loader + comparison-table renderer.

``hub/registry.yaml`` is the source of truth for the per-model comparison
table (a hosted hub site is planned, not yet implemented). This module loads it into
structured rows and renders a Markdown table.

It lives in the installed package (not ``scripts/``) so the platform CLI
(``omnidocbench-rocm list``) can import it without a ``scripts/`` path hack
(ADR-0005: the adapter contract is the single integration seam, and the
discovery layer reuses the same registry model the hub renders from).
``scripts/generate_registry.py`` is now a thin wrapper that re-exports this
module for hub authors.

Public API:
    generate_registry(yaml_path) -> list[dict]
    render_table(rows) -> str
    render_hub(rows, external_ref_url=None) -> str
    _best_badge(row) -> str

Row schema (one dict per model)::

    {
        "model_id": "paddleocr-vl-1.6",
        "repo": "AIwork4me/PaddleOCR-VL-ROCm",
        "platforms": {
            "linux-rocm":  {"badge": "verified", "overall": 95.94},
            "windows-hip": {"badge": "community-wanted", "overall": None},
        },
    }

Badge policy (``contracts/badge-policy``): one of
``verified`` | ``community`` | ``community-wanted``. ``overall`` is the
OmniDocBench v1.6 overall score (number) or ``null`` when not yet measured.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Columns rendered in the comparison table, in order.
COLUMNS = ("Model", "Repo", "License", "linux-rocm", "windows-hip")


def generate_registry(yaml_path: Path | str) -> list[dict]:
    """Load ``hub/registry.yaml`` into a list of model row dicts.

    Returns an empty list when the YAML is empty / ``null`` so callers can
    always iterate without a None-check.
    """
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    return data or []


def render_table(rows: list[dict]) -> str:
    """Render model rows as a 5-column Markdown comparison table.

    Columns: ``Model | Repo | License | linux-rocm | windows-hip``. Each
    platform cell shows ``<badge> (<overall>)``; an absent platform renders as
    an em-dash. The License cell shows ``row["license"]`` or an em-dash when
    unset. The Model cell shows the official display name ``row["name"]``,
    falling back to ``model_id`` when no name is declared. The Repo cell is a
    clickable ``[owner/repo](https://github.com/owner/repo)`` link.
    """
    lines = [
        f"| {' | '.join(COLUMNS)} |",
        f"|{'|'.join(['---'] * len(COLUMNS))}|",
    ]
    for r in rows:
        platforms = r.get("platforms", {}) or {}
        repo = r.get("repo", "")
        repo_cell = f"[{repo}](https://github.com/{repo})" if repo else "—"
        lines.append(
            "| {model} | {repo} | {license} | {linux} | {windows} |".format(
                model=r.get("name") or r.get("model_id", ""),
                repo=repo_cell,
                license=r.get("license") or "—",
                linux=_cell(platforms.get("linux-rocm")),
                windows=_cell(platforms.get("windows-hip")),
            )
        )
    return "\n".join(lines)


# Tier = a model's *best* badge across platforms: verified > community > community-wanted.
_BADGE_RANK = {"verified": 3, "community": 2, "community-wanted": 1}


def _best_badge(row: dict) -> str:
    """Return a model's highest-ranked platform badge.

    Scans every platform entry's ``badge``; an entry lacking one defaults to
    ``community-wanted``. A model with no platforms is also ``community-wanted``.
    """
    plats = row.get("platforms", {}) or {}
    badges = [v.get("badge", "community-wanted") for v in plats.values() if isinstance(v, dict)]
    return max(badges, key=lambda b: _BADGE_RANK.get(b, 0)) if badges else "community-wanted"


def render_hub(rows: list[dict], external_ref_url: str | None = None) -> str:
    """Render rows as a 3-tier hub comparison: Flagship / Community / Incoming.

    Each model lands in the section matching its best badge (verified ->
    Flagship, community -> Community, community-wanted -> Incoming). Sections
    are emitted only when non-empty, joined by blank lines. When
    ``external_ref_url`` is given, a final link section is appended naming the
    OmniDocBench paper as cited-but-not-reproduced. Returns ``(no models)``
    when no rows produced any section.
    """
    flagship, community, incoming = [], [], []
    for r in rows:
        {"verified": flagship, "community": community}.get(_best_badge(r), incoming).append(r)
    parts = []
    if flagship:
        parts.append("## Flagship comparison (verified)\n\n" + render_table(flagship))
    if community:
        parts.append("## Community (also evaluated)\n\n" + render_table(community))
    if incoming:
        parts.append("## Incoming (community-wanted)\n\n" + render_table(incoming))
    if external_ref_url:
        parts.append(
            "## External reference\n\n"
            "Closed-SOTA calibration: [OmniDocBench paper](" + external_ref_url +
            ") — cited, not reproduced here, never badged.")
    return "\n\n".join(parts) if parts else "(no models)"


def _cell(c: dict | None) -> str:
    """Format a per-platform entry as ``<badge> (<overall>)``.

    ``None`` (platform absent / not yet listed) renders as an em-dash.
    A ``null`` overall renders as an empty pair of parens to preserve the
    badge while signalling the score is pending.
    """
    if not c:
        return "—"
    overall = c.get("overall")
    overall_str = "" if overall is None else str(overall)
    return f"{c['badge']} ({overall_str})"


# ---------------------------------------------------------------------------
# Single source of truth — canonical results + generated README section (ADR-0012)
# ---------------------------------------------------------------------------
# Data flow:  hub/canonical_results.json  (the ONLY place scores live)
#                 -> README generated-results section  (derived, never hand-written)
#                 -> hub comparison table              (registry.yaml mirror, checked)
# `python -m omnidocbench_rocm.registry generate`        rewrites the section
# `python -m omnidocbench_rocm.registry generate --check` fails on drift (CI)
# The primary result is NEVER auto-picked by score — it is an explicit choice.

CANONICAL_RESULTS_PATH = "hub/canonical_results.json"
BEGIN_MARKER = "<!-- BEGIN GENERATED RESULTS -->"
END_MARKER = "<!-- END GENERATED RESULTS -->"
_HIDDEN_STATUSES = ("retracted", "invalid")  # never shown in the public results list

import json as _json
from .schema import iter_validation_errors as _iter_errors


def load_canonical(path: Path | str = CANONICAL_RESULTS_PATH) -> list[dict]:
    """Load + schema-validate the canonical results store (single source of truth).

    Returns the entries sorted deterministically by (model_id, platform, result_id).
    Raises ``ValueError`` listing every schema problem so a stale/corrupt store is
    caught at load time, not silently rendered.
    """
    data = _json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["results"] if isinstance(data, dict) else data
    problems: list[str] = []
    for i, row in enumerate(rows):
        problems += [f"canonical_results[{i}]: {m}" for m in _iter_errors("canonical_result", row)]
    # result_id uniqueness
    ids = [r.get("result_id") for r in rows]
    dups = sorted({x for x in ids if ids.count(x) > 1})
    for d in dups:
        problems.append(f"canonical_results: duplicate result_id {d!r}")
    if problems:
        raise ValueError("invalid canonical_results:\n  - " + "\n  - ".join(problems))
    return sorted(rows, key=lambda r: (r.get("model_id", ""), r.get("platform", ""), r.get("result_id", "")))


def _registry_index(yaml_path: Path | str) -> dict[str, dict]:
    """model_id -> registry row (for license/notes lookup)."""
    return {r.get("model_id"): r for r in generate_registry(yaml_path)}


def render_results_section(canonical: list[dict], yaml_path: Path | str = "hub/registry.yaml") -> str:
    """Render the deterministic, no-hand-written-score results table.

    Hidden statuses (retracted/invalid) are excluded from the list but counted in
    a footer note. No result is implicitly primary (ADR-0012).
    """
    reg = _registry_index(yaml_path)
    shown = [r for r in canonical if r.get("status") not in _HIDDEN_STATUSES]
    hidden = [r for r in canonical if r.get("status") in _HIDDEN_STATUSES]
    lines = [
        BEGIN_MARKER,
        "<!-- generated by `python -m omnidocbench_rocm.registry generate` — do not edit by hand. -->",
        "<!-- Scores come ONLY from hub/canonical_results.json (ADR-0012 single source of truth). -->",
        "",
        "| Model | Platform | Overall | Assurance | License | Status |",
        "|---|---|---|---|---|---|",
    ]
    for r in shown:
        row = reg.get(r["model_id"], {})
        lic = r.get("license_category") or _row_license_category(row)
        overall = r.get("overall")
        overall_str = "—" if overall is None else f"{overall}"
        note = f" ({r['status']})" if r.get("status") and r["status"] != "valid" else ""
        lines.append(
            f"| `{r['model_id']}` | {r['platform']} | {overall_str} | "
            f"{r.get('assurance', 'submitted')} | {lic} | {r.get('status', 'valid')}{note} |"
        )
    if hidden:
        lines.append("")
        lines.append(f"<sub>{len(hidden)} result(s) hidden (status "
                     f"{'/'.join(_HIDDEN_STATUSES)}); retained in canonical_results.json, "
                     "never deleted.</sub>")
    lines.append(END_MARKER)
    return "\n".join(lines)


def _row_license_category(row: dict) -> str:
    return row.get("license_category") or "unknown"


def _read_section(text: str) -> str | None:
    """Return the current generated-results block (markers inclusive) or None."""
    i = text.find(BEGIN_MARKER)
    j = text.find(END_MARKER)
    if i == -1 or j == -1 or j < i:
        return None
    return text[i:j + len(END_MARKER)]


def generate(registry_yaml: Path | str = "hub/registry.yaml",
             canonical_path: Path | str = CANONICAL_RESULTS_PATH,
             readme: Path | str = "README.md", *, write: bool = True) -> dict:
    """Regenerate the README results section from canonical_results.json.

    Returns a report dict ``{section, changed, hidden}``. When ``write`` is False
    the README is not touched (dry run).
    """
    canonical = load_canonical(canonical_path)
    section = render_results_section(canonical, registry_yaml)
    readme_p = Path(readme)
    text = readme_p.read_text(encoding="utf-8") if readme_p.exists() else ""
    current = _read_section(text)
    changed = current != section
    if write and changed:
        if current is None:
            # append the section at the end if markers are absent
            text = text.rstrip() + "\n\n" + section + "\n"
        else:
            text = text[:text.find(BEGIN_MARKER)] + section + text[text.find(END_MARKER) + len(END_MARKER):]
        readme_p.write_text(text, encoding="utf-8")
    return {"section": section, "changed": changed,
            "hidden": sum(1 for r in canonical if r.get("status") in _HIDDEN_STATUSES)}


def check(registry_yaml: Path | str = "hub/registry.yaml",
          canonical_path: Path | str = CANONICAL_RESULTS_PATH,
          readme: Path | str = "README.md") -> tuple[bool, list[str]]:
    """Verify the generated section is up to date + canonical/registry consistent.

    Returns ``(ok, problems)``. Problems include: README section drift, registry
    platform overall != canonical overall, and measured registry platforms with
    no canonical entry. ``ok`` is False on any problem (CI fails).
    """
    problems: list[str] = []
    canonical = load_canonical(canonical_path)
    section = render_results_section(canonical, registry_yaml)
    readme_p = Path(readme)
    text = readme_p.read_text(encoding="utf-8") if readme_p.exists() else ""
    current = _read_section(text)
    if current is None:
        problems.append(f"README missing {BEGIN_MARKER} ... {END_MARKER} block")
    elif current != section:
        problems.append("README generated-results section is stale — run "
                        "`python -m omnidocbench_rocm.registry generate`")

    # cross-check: registry.yaml platform overall must mirror canonical.
    # Multiple VALID canonical results per (model, platform) are ALLOWED (multi-
    # backend, ADR-0016/0017) — the registry mirrors the one flagged `primary`
    # (ADR-0012/0016). Only flag ambiguity when no single primary is designated.
    reg_by_id = _registry_index(registry_yaml)
    canon_by_key: dict[tuple[str, str], list[dict]] = {}
    for r in canonical:
        if r.get("status") != "valid":
            continue
        canon_by_key.setdefault((r.get("model_id", ""), r.get("platform", "")), []).append(r)
    canon_pairs: dict[tuple[str, str], dict] = {}
    for key, rs in canon_by_key.items():
        if len(rs) == 1:
            canon_pairs[key] = rs[0]
            continue
        primaries = [r for r in rs if r.get("primary") is True]
        if len(primaries) == 1:
            canon_pairs[key] = primaries[0]            # multi-backend OK; primary represents
        elif len(primaries) == 0:
            problems.append(f"multiple valid canonical results for {key} with no `primary` "
                            "designated (ambiguous — set primary, ADR-0016)")
            canon_pairs[key] = rs[0]
        else:
            problems.append(f"multiple `primary` canonical results for {key} (ambiguous)")
            canon_pairs[key] = primaries[0]
    for mid, row in reg_by_id.items():
        for plat, entry in (row.get("platforms") or {}).items():
            if not isinstance(entry, dict):
                continue
            reg_overall = entry.get("overall")
            if reg_overall is None:
                # community-wanted / unmeasured -> must NOT have a canonical entry
                if (mid, plat) in canon_pairs:
                    problems.append(f"registry {mid}/{plat} overall is null but canonical_results "
                                    "has an entry (drift)")
                continue
            canon = canon_pairs.get((mid, plat))
            if canon is None:
                problems.append(f"registry {mid}/{plat} overall {reg_overall} has no matching "
                                "canonical_results entry")
            elif round(float(reg_overall), 2) != round(float(canon.get("overall") or 0), 2):
                problems.append(f"registry {mid}/{plat} overall {reg_overall} != canonical "
                                f"{canon.get('overall')} (canonical is the source of truth)")
    return (len(problems) == 0), problems


def _main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m omnidocbench_rocm.registry",
                                 description="Generate / check the canonical-results README section.")
    sub = ap.add_subparsers(dest="cmd")
    g = sub.add_parser("generate", help="regenerate the README results section from canonical_results.json")
    g.add_argument("--check", action="store_true", help="fail (exit 1) if the section would change / drifts")
    g.add_argument("--registry", default="hub/registry.yaml")
    g.add_argument("--canonical", default=CANONICAL_RESULTS_PATH)
    g.add_argument("--readme", default="README.md")
    a = ap.parse_args(argv)
    if a.cmd == "generate":
        if a.check:
            ok, problems = check(a.registry, a.canonical, a.readme)
            if ok:
                print("generated-results: up to date ✓"); return 0
            print("generated-results: DRIFT / INVALID")
            for p in problems:
                print(" -", p)
            return 1
        report = generate(a.registry, a.canonical, a.readme, write=True)
        print(f"generated-results: {'updated' if report['changed'] else 'already up to date'} "
              f"({report['hidden']} hidden)")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

