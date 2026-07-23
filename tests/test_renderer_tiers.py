"""Tests for the 3-tier hub renderer (ADR-0003/0004).

``render_hub`` splits model rows into Flagship (verified), Community (also
evaluated) and Incoming (community-wanted) sections, plus an optional
external-reference link section. A model's tier is its *best* badge across
platforms: ``verified > community > community-wanted``.
"""
ROWS = [
    {"model_id": "a", "repo": "AIwork4me/A-ROCm", "license": "Apache-2.0", "commercial_use": "none",
     "platforms": {"linux-rocm": {"badge": "verified", "overall": 95.0}}},
    {"model_id": "b", "repo": "AIwork4me/B-ROCm", "license": "MIT", "commercial_use": "none",
     "platforms": {"linux-rocm": {"badge": "community", "overall": 93.0}}},
    {"model_id": "c", "repo": "AIwork4me/C-ROCm", "license": "Apache-2.0", "commercial_use": "none",
     "platforms": {"linux-rocm": {"badge": "community-wanted", "overall": None}}},
]


def test_render_hub_splits_three_tiers():
    from scripts.generate_registry import render_hub
    out = render_hub(ROWS)
    assert "Flagship comparison (verified)" in out and "| a " in out
    assert "Community (also evaluated)" in out and "| b " in out
    assert "Incoming (community-wanted)" in out and "| c " in out
    # c must NOT appear in the flagship section
    flagship = out.split("## Community")[0]
    assert "| c " not in flagship


def test_render_hub_external_reference_is_link_only():
    from scripts.generate_registry import render_hub
    out = render_hub(ROWS, external_ref_url="https://example.com/paper")
    assert "External reference" in out
    assert "https://example.com/paper" in out


def test_render_table_shows_license_column():
    from scripts.generate_registry import render_table
    out = render_table(ROWS[:1])
    assert "| License |" in out
    assert "| Apache-2.0 |" in out
