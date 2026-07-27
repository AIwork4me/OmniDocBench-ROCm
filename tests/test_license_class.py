"""Tests for the license / open-source classification (ADR-0010)."""
import pytest
from omnidocbench_rocm.license_class import (
    LICENSE_CATEGORIES, classify, build_license_record, validate_license_record,
    assert_no_default_open_source,
)


def test_known_licenses_classify():
    assert classify("MIT") == "open-source-ai"
    assert classify("Apache-2.0") == "open-source-ai"
    assert classify("MinerU Open Source License") == "restricted"
    assert classify("Tencent Hunyuan Community License") == "restricted"


def test_unknown_license_never_open_source():
    # The cardinal rule: unrecognized -> unknown, never open-source-ai
    assert classify("Some Weird License 9000") == "unknown"
    assert classify("") == "unknown"
    assert classify(None) == "unknown"


def test_build_license_record_carries_restrictions():
    rec = build_license_record(name="Tencent Hunyuan Community License")
    assert rec["category"] == "restricted"
    assert "commercial" in rec["commercial_use"].lower() or rec["commercial_use"]
    validate_license_record(rec)


def test_build_license_record_rejects_bad_category():
    with pytest.raises(Exception):
        build_license_record(category="open-source")  # not a valid category


def test_no_default_open_source_guard():
    # An open-source-ai claim with no backing license is flagged (the unsafe default).
    with pytest.raises(ValueError):
        assert_no_default_open_source({"category": "open-source-ai"})
    # ...but a known-permissive SPDX backs it, so it passes.
    assert_no_default_open_source({"category": "open-source-ai", "spdx": "Apache-2.0"})
    # unknown is always fine.
    assert_no_default_open_source({"category": "unknown"})


def test_all_categories_present():
    expected = {"open-source-ai", "open-weights", "source-available",
                "restricted", "closed", "unknown"}
    assert set(LICENSE_CATEGORIES) == expected
