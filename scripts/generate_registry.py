"""Thin wrapper around :mod:`omnidocbench_rocm.registry`.

The registry loader + table/hub renderers now live in the installed package
(``omnidocbench_rocm.registry``) so the platform CLI can import them without a
``scripts/`` path hack (ADR-0005). This module re-exports them for hub
authors who run the script directly and keeps the legacy ``__main__`` CLI.

Public API (re-exported):
    generate_registry, render_table, render_hub, _best_badge, _cell, COLUMNS
"""
from __future__ import annotations

# Make `scripts/` importable from the repo root so this wrapper can import the
# package when run as a standalone script (e.g. `python scripts/generate_registry.py`).
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from omnidocbench_rocm.registry import (  # noqa: E402,F401
    COLUMNS,
    _best_badge,
    _cell,
    generate_registry,
    render_hub,
    render_table,
)

__all__ = ["generate_registry", "render_table", "render_hub", "_best_badge", "_cell", "COLUMNS"]


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
    # render_hub (3-tier Flagship/Community/Incoming) is what the README
    # <!-- registry-table --> block holds; the CI drift gate compares against this.
    print(render_hub(generate_registry(args.yaml_path)))
