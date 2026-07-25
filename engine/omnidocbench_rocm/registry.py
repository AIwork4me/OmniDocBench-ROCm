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
    unset.
    """
    lines = [
        f"| {' | '.join(COLUMNS)} |",
        f"|{'|'.join(['---'] * len(COLUMNS))}|",
    ]
    for r in rows:
        platforms = r.get("platforms", {}) or {}
        lines.append(
            "| {model} | {repo} | {license} | {linux} | {windows} |".format(
                model=r.get("model_id", ""),
                repo=r.get("repo", ""),
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
