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
    import sys

    ap = argparse.ArgumentParser(description="Render hub/registry.yaml to a Markdown table.")
    ap.add_argument(
        "yaml_path",
        nargs="?",
        default="hub/registry.yaml",
        help="Path to registry.yaml (default: hub/registry.yaml).",
    )
    ap.add_argument("--check", action="store_true",
                    help="compare the rendered table to the README <!-- registry-table --> "
                         "block; exit 1 on drift (the CI freshness gate).")
    args = ap.parse_args()
    table = render_hub(generate_registry(args.yaml_path))
    if args.check:
        import re
        readme = Path("README.md").read_text(encoding="utf-8") if Path("README.md").exists() else ""
        m = re.search(r"<!-- registry-table -->\n(.*?)\n<!-- /registry-table -->", readme, re.S)
        current = m.group(1) if m else ""
        current = re.sub(r"^<!-- generated.*-->\n", "", current, flags=re.M)
        # normalize blank lines for the comparison (matches the ci.yml gate)
        norm = lambda s: "\n".join(x for x in s.splitlines() if x.strip())
        if norm(table) != norm(current):
            print("ERROR: README <!-- registry-table --> block is stale — run `make hub-regen`.",
                  file=sys.stderr)
            sys.exit(1)
        print("comparison-table: up to date ✓")
    else:
        # render_hub (3-tier Flagship/Community/Incoming) is what the README
        # <!-- registry-table --> block holds; the CI drift gate compares against this.
        print(table)
