"""Tests for the canonical-results single source of truth + drift check (ADR-0012)."""
import json
import shutil
from pathlib import Path
import pytest
from omnidocbench_rocm.registry import (
    load_canonical, render_results_section, generate, check,
    BEGIN_MARKER, END_MARKER,
)

REPO = Path(__file__).resolve().parents[1]
CANON = REPO / "hub" / "canonical_results.json"
REG = REPO / "hub" / "registry.yaml"


def test_canonical_results_load_and_unique_ids():
    rows = load_canonical(CANON)
    assert rows  # non-empty
    ids = [r["result_id"] for r in rows]
    assert len(ids) == len(set(ids)), "result_ids must be unique"


def test_render_is_deterministic():
    rows = load_canonical(CANON)
    assert render_results_section(rows, REG) == render_results_section(rows, REG)


def test_retracted_hidden_from_render():
    rows = load_canonical(CANON)
    section = render_results_section(rows, REG)
    # the retracted example (overall 91.0) must NOT appear in the public table
    assert "91.0" not in section or "91.00" not in section
    # but a hidden-results footer is present (retained, never deleted)
    assert "hidden" in section
    # the retracted row itself is absent from the table body
    retracted = [r for r in rows if r.get("status") == "retracted"]
    if retracted:
        # its overall must not be rendered as a visible result row
        for r in retracted:
            line = f"| `{r['model_id']}` | {r['platform']} | {r['overall']} |"
            assert line not in section


def test_no_auto_primary_in_section():
    # The generated section lists results flat; it never picks a "primary" by score.
    section = render_results_section(load_canonical(CANON), REG)
    assert "primary" not in section.lower()


def test_generate_then_check_passes_on_real_repo(tmp_path):
    # Copy real inputs into tmp so we don't mutate the repo.
    work = tmp_path
    shutil.copy(CANON, work / "canonical.json")
    shutil.copy(REG, work / "registry.yaml")
    # seed a README with empty markers
    (work / "README.md").write_text(f"# R\n\n{BEGIN_MARKER}\n{END_MARKER}\n", encoding="utf-8")
    generate(work / "registry.yaml", work / "canonical.json", work / "README.md", write=True)
    ok, problems = check(work / "registry.yaml", work / "canonical.json", work / "README.md")
    assert ok, problems


def test_check_detects_readme_drift(tmp_path):
    work = tmp_path
    shutil.copy(CANON, work / "canonical.json")
    shutil.copy(REG, work / "registry.yaml")
    # README with stale (wrong) section
    (work / "README.md").write_text(
        f"# R\n\n{BEGIN_MARKER}\nSTALE CONTENT\n{END_MARKER}\n", encoding="utf-8")
    ok, problems = check(work / "registry.yaml", work / "canonical.json", work / "README.md")
    assert not ok
    assert any("stale" in p or "missing" in p for p in problems)


def test_check_detects_score_drift_between_canonical_and_registry(tmp_path):
    work = tmp_path
    shutil.copy(CANON, work / "canonical.json")
    reg_text = REG.read_text(encoding="utf-8")
    # tamper one registry overall so it disagrees with canonical
    reg_text2 = reg_text.replace("95.88", "95.99", 1)
    (work / "registry.yaml").write_text(reg_text2, encoding="utf-8")
    (work / "README.md").write_text(
        render_results_section(load_canonical(work / "canonical.json"), work / "registry.yaml"),
        encoding="utf-8")
    ok, problems = check(work / "registry.yaml", work / "canonical.json", work / "README.md")
    assert not ok
    assert any("!= canonical" in p for p in problems)


def test_generate_idempotent(tmp_path):
    work = tmp_path
    shutil.copy(CANON, work / "canonical.json")
    shutil.copy(REG, work / "registry.yaml")
    (work / "README.md").write_text(f"{BEGIN_MARKER}\n{END_MARKER}\n", encoding="utf-8")
    g1 = generate(work / "registry.yaml", work / "canonical.json", work / "README.md", write=True)
    g2 = generate(work / "registry.yaml", work / "canonical.json", work / "README.md", write=True)
    assert g1["section"] == g2["section"]
    assert g2["changed"] is False  # second run is a no-op


def test_canonical_entries_schema_valid():
    from omnidocbench_rocm.schema import iter_validation_errors
    rows = json.loads(CANON.read_text(encoding="utf-8"))["results"]
    for i, r in enumerate(rows):
        errs = iter_validation_errors("canonical_result", r)
        assert not errs, f"canonical_results[{i}] invalid: {errs}"
