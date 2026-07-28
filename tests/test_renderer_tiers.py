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
    from omnidocbench_rocm.registry import render_hub
    out = render_hub(ROWS)
    assert "Flagship comparison (verified)" in out and "| a " in out
    assert "Community (also evaluated)" in out and "| b " in out
    assert "Incoming (community-wanted)" in out and "| c " in out
    # c must NOT appear in the flagship section
    flagship = out.split("## Community")[0]
    assert "| c " not in flagship


def test_render_hub_external_reference_is_link_only():
    from omnidocbench_rocm.registry import render_hub
    out = render_hub(ROWS, external_ref_url="https://example.com/paper")
    assert "External reference" in out
    assert "https://example.com/paper" in out


def test_render_table_shows_license_column():
    from omnidocbench_rocm.registry import render_table
    out = render_table(ROWS[:1])
    assert "| License |" in out
    assert "| Apache-2.0 |" in out


def test_render_table_uses_display_name_and_links_repo():
    """Model column shows the official ``name`` (not the model_id slug); Repo is a link.

    Rows without ``name`` keep falling back to ``model_id`` — that path is covered
    by the tier tests above (rows a/b/c carry no ``name`` and still render their id).
    """
    from omnidocbench_rocm.registry import render_table
    row = {
        "model_id": "paddleocr-vl-1.6",
        "name": "PaddleOCR-VL 1.6",
        "repo": "AIwork4me/PaddleOCR-VL-ROCm",
        "license": "Apache-2.0",
        "platforms": {"linux-rocm": {"badge": "community", "overall": 95.77}},
    }
    out = render_table([row])
    # official display name is the Model cell; the lowercase slug is NOT shown
    assert "| PaddleOCR-VL 1.6 |" in out
    assert "paddleocr-vl-1.6" not in out
    # Repo is a clickable github link, not bare text
    assert "[AIwork4me/PaddleOCR-VL-ROCm](https://github.com/AIwork4me/PaddleOCR-VL-ROCm)" in out
