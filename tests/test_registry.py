"""Tests for the hub model registry + comparison-table generator.

Covers Task 11: ``hub/registry.yaml`` is the source of truth for the hub
comparison table; ``scripts/generate_registry.py`` loads it into structured
rows and renders a Markdown table consumed by the mkdocs hub site.
"""
from pathlib import Path

from scripts.generate_registry import generate_registry, render_table

REG = """
- model_id: paddleocr-vl-1.6
  repo: AIwork4me/PaddleOCR-VL-ROCm
  platforms:
    linux-rocm: {badge: verified, overall: 95.94}
    windows-hip: {badge: community, overall: 95.94}
- model_id: unlimited-ocr
  repo: AIwork4me/Unlimited-OCR-ROCm
  platforms:
    linux-rocm: {badge: verified, overall: 92.43}
    windows-hip: {badge: community-wanted, overall: null}
"""


def test_generate_registry(tmp_path):
    y = tmp_path / "registry.yaml"
    y.write_text(REG)
    rows = generate_registry(y)
    assert len(rows) == 2
    # Per-platform badges resolve through the nested platforms dict.
    assert rows[0]["platforms"]["linux-rocm"]["badge"] == "verified"
    assert rows[1]["platforms"]["windows-hip"]["badge"] == "community-wanted"
    # model_id + repo are present on each row.
    assert rows[0]["model_id"] == "paddleocr-vl-1.6"
    assert rows[1]["repo"] == "AIwork4me/Unlimited-OCR-ROCm"
    # overall numeric + null both survive the YAML round-trip.
    assert rows[0]["platforms"]["linux-rocm"]["overall"] == 95.94
    assert rows[1]["platforms"]["windows-hip"]["overall"] is None


def test_render_table():
    rows = generate_registry_from_text(REG)
    md = render_table(rows)
    lines = md.splitlines()
    # Header + separator + one row per model.
    assert lines[0] == "| Model | Repo | linux-rocm | windows-hip |"
    assert lines[1] == "|---|---|---|---|"
    assert len(lines) == 2 + len(rows)
    # Body cells carry badge + overall (or em-dash placeholder for null).
    assert "paddleocr-vl-1.6" in lines[2]
    assert "verified" in lines[2]
    assert "95.94" in lines[2]
    assert "community-wanted" in lines[3]
    # The four expected columns are present in the header.
    for col in ("Model", "Repo", "linux-rocm", "windows-hip"):
        assert col in lines[0]


def test_render_table_empty():
    """An empty registry yields a header-only table (no body rows)."""
    md = render_table([])
    lines = md.splitlines()
    assert lines[0] == "| Model | Repo | linux-rocm | windows-hip |"
    assert lines[1] == "|---|---|---|---|"
    assert len(lines) == 2


def generate_registry_from_text(text: str) -> list[dict]:
    """Helper: load rows from an inline YAML string (avoids tmp file in render test)."""
    import io

    import yaml

    return yaml.safe_load(io.StringIO(text)) or []
