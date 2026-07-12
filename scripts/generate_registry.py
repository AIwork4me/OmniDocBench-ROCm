"""Hub model registry loader + comparison-table renderer.

``hub/registry.yaml`` is the source of truth for the per-model comparison
table on the hub site (mkdocs, sub-project 1). This module loads it into
structured rows and renders a Markdown table.

Public API:
    generate_registry(yaml_path) -> list[dict]
    render_table(rows) -> str

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
COLUMNS = ("Model", "Repo", "linux-rocm", "windows-hip")


def generate_registry(yaml_path: Path | str) -> list[dict]:
    """Load ``hub/registry.yaml`` into a list of model row dicts.

    Returns an empty list when the YAML is empty / ``null`` so callers can
    always iterate without a None-check.
    """
    data = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
    return data or []


def render_table(rows: list[dict]) -> str:
    """Render model rows as a 4-column Markdown comparison table.

    Columns: ``Model | Repo | linux-rocm | windows-hip``. Each platform cell
    shows ``<badge> (<overall>)``; an absent platform renders as an em-dash.
    """
    lines = [
        f"| {' | '.join(COLUMNS)} |",
        f"|{'|'.join(['---'] * len(COLUMNS))}|",
    ]
    for r in rows:
        platforms = r.get("platforms", {}) or {}
        lines.append(
            "| {model} | {repo} | {linux} | {windows} |".format(
                model=r.get("model_id", ""),
                repo=r.get("repo", ""),
                linux=_cell(platforms.get("linux-rocm")),
                windows=_cell(platforms.get("windows-hip")),
            )
        )
    return "\n".join(lines)


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


if __name__ == "__main__":  # pragma: no cover - manual CLI for hub authors
    import argparse

    ap = argparse.ArgumentParser(description="Render hub/registry.yaml to a Markdown table.")
    ap.add_argument(
        "yaml_path",
        nargs="?",
        default="hub/registry.yaml",
        help="Path to registry.yaml (default: hub/registry.yaml).",
    )
    args = ap.parse_args()
    print(render_table(generate_registry(args.yaml_path)))
