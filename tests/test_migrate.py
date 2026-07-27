"""Tests for the v1 -> v2 model-card migration (ADR-0007)."""
import json
from pathlib import Path
import pytest
from omnidocbench_rocm.migrate import migrate_v1_to_v2, migrate_file
from omnidocbench_rocm.model_card_v2 import validate_card_v2, make_result_id

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_migrate_v1_fixture_to_valid_v2():
    v1 = _load("v1_model_card.json")
    v2, report = migrate_v1_to_v2(v1)
    assert report["migrated"] is True
    assert v2["schema_version"] == 2
    assert validate_card_v2(v2) == []
    # linux-rocm was the only measured platform (community); windows-hip was community-wanted
    assert [r["coverage"]["platform"] for r in v2["results"]] == ["linux-rocm"]
    primary = next(r for r in v2["results"] if r.get("primary"))
    assert primary["metrics"]["overall"] == 95.12            # overall carried to primary
    assert primary["assurance"] == "evidence-complete"        # community -> evidence-complete


def test_migrate_is_idempotent_on_v2():
    v2 = _load("v2_model_card.json")
    again, report = migrate_v1_to_v2(v2)
    assert report["already_v2"] is True
    assert again == v2  # idempotent on v2 input


def test_migrate_double_application_stable():
    v1 = _load("v1_model_card.json")
    once, _ = migrate_v1_to_v2(v1)
    twice, _ = migrate_v1_to_v2(once)
    assert once == twice  # migrate(migrate(x)) == migrate(x)


def test_migrate_does_not_guess_fields():
    v1 = _load("v1_model_card.json")
    _, report = migrate_v1_to_v2(v1)
    # git_commit / precision / page_count / dataset hashes are not in v1 -> listed, not invented
    carried = " ".join(report["fields_not_carried"])
    assert "git_commit" in carried
    assert "precision" in carried
    # the migrated result must NOT carry a fabricated git_commit
    v2, _ = migrate_v1_to_v2(v1)
    prov = v2["results"][0].get("provenance", {})
    assert "git_commit" not in prov or prov.get("git_commit") in ("", None)


def test_migrate_result_id_reproducible():
    v1 = _load("v1_model_card.json")
    v2, _ = migrate_v1_to_v2(v1)
    rid = v2["results"][0]["result_id"]
    expected = make_result_id(model_id="fixture-vlm", platform="linux-rocm",
                              backend="vllm", benchmark_version="v1.6")
    assert rid == expected


def test_migrate_check_exit_codes(tmp_path):
    # v1 input -> check exits 1 (needs migration)
    _, _, ec = migrate_file(FIX / "v1_model_card.json", check=True)
    assert ec == 1
    # v2 input -> check exits 0 (already v2)
    _, _, ec2 = migrate_file(FIX / "v2_model_card.json", check=True)
    assert ec2 == 0


def test_migrate_in_place_and_output(tmp_path):
    dst = tmp_path / "card.json"
    dst.write_text((FIX / "v1_model_card.json").read_text(encoding="utf-8"), encoding="utf-8")
    migrate_file(dst, in_place=True)
    assert json.loads(dst.read_text(encoding="utf-8"))["schema_version"] == 2

    out = tmp_path / "out.json"
    migrate_file(FIX / "v1_model_card.json", output=out)
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == 2


def test_migrate_restricted_license_classified():
    v1 = {"schema_version": 1, "model_id": "m", "platforms": ["linux-rocm"],
          "badge": {"linux-rocm": "community"}, "overall": 90.0,
          "license": "MinerU Open Source License", "commercial_use": "threshold"}
    v2, report = migrate_v1_to_v2(v1)
    assert v2["license"]["category"] == "restricted"
    # a KNOWN restrictive license must NOT trigger an 'unknown' warning
    assert not any("unknown" in w for w in report["warnings"])


def test_migrate_multi_platform_single_overall_projection():
    # v1 with two MEASURED platforms but one overall -> primary carries it, other gets null
    v1 = {"schema_version": 1, "model_id": "m", "platforms": ["linux-rocm", "windows-hip"],
          "badge": {"linux-rocm": "community", "windows-hip": "community"},
          "overall": 90.0, "omnidocbench_version": "v1.6"}
    v2, report = migrate_v1_to_v2(v1)
    overalls = {r["coverage"]["platform"]: r["metrics"]["overall"] for r in v2["results"]}
    assert overalls["linux-rocm"] == 90.0      # primary
    assert overalls["windows-hip"] is None      # honest: not attributed
    assert report["primary_platform"] == "linux-rocm"
