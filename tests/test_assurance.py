"""Tests for the assurance level system (ADR-0008)."""
import pytest
from omnidocbench_rocm import assurance


def test_levels_and_order():
    assert assurance.ASSURANCE_LEVELS == (
        "submitted", "evidence-complete", "score-reproduced",
        "inference-reproduced", "cross-hardware-reproduced")
    assert assurance.ASSURANCE_RANK["submitted"] < assurance.ASSURANCE_RANK["cross-hardware-reproduced"]


def test_strongest_picks_highest():
    levels = ["submitted", "score-reproduced", "evidence-complete"]
    assert assurance.strongest(levels) == "score-reproduced"
    assert assurance.strongest([]) == "submitted"


def test_legacy_projection_roundtrip():
    for badge in ("community", "verified", "community-wanted"):
        a = assurance.assurance_from_legacy_badge(badge)
        assurance.assert_valid(a)
    assert assurance.legacy_badge_from_assurance("score-reproduced") == "verified"
    assert assurance.legacy_badge_from_assurance("evidence-complete") == "community"


def test_per_result_validation_flags_missing_and_bad():
    problems = assurance.validate_results_assurance([
        {"assurance": "evidence-complete"},
        {"assurance": None},
        {"assurance": "trusted"},  # not a level
    ])
    assert any("missing assurance" in p for p in problems)
    assert any("unknown assurance" in p for p in problems)


def test_no_propagation_detects_model_wide_fields():
    # A model-wide assurance/badge/verified implies cross-result propagation.
    assert set(assurance.check_no_propagation({"badge": {"linux-rocm": "community"}})) == {"badge"}
    assert assurance.check_no_propagation({"assurance": "verified"}) == ["assurance"]
    assert assurance.check_no_propagation({"verified": True}) == ["verified"]
    assert assurance.check_no_propagation({"results": []}) == []


def test_assurance_does_not_leak_between_results():
    # assurance lives per-result; one result's level says nothing about another.
    results = [
        {"result_id": "a", "assurance": "score-reproduced"},
        {"result_id": "b", "assurance": "submitted"},
    ]
    assert assurance.validate_results_assurance(results) == []
    # strongest collapses only for lossy display, never mutates the records
    assert results[0]["assurance"] == "score-reproduced"
    assert results[1]["assurance"] == "submitted"
