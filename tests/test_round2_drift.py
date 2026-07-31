"""Cross-repo drift + license separation (Round-2, §13 26-30)."""
import json
import pytest
from omnidocbench_rocm import hub
from omnidocbench_rocm.schema import validate_artifact, iter_validation_errors


def test_default_default_identity_flagged():
    rows = [{"result_id": "x__linux-rocm__default__default__v1-6__abc",
             "status": "valid", "backend": "", "precision": "",
             "overall": 95.0, "assurance": "evidence-complete"}]
    f = hub.check_drift(canonical_rows=rows)
    kinds = [x["kind"] for x in f]
    assert "default-default-identity" in kinds


def test_missing_source_flagged():
    rows = [{"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "fp16",
             "overall": 90.0}]
    f = hub.check_drift(canonical_rows=rows)
    assert any(x["kind"] == "missing-source" for x in f)


def test_registry_score_not_a_fact_source():
    rows = [{"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "fp16",
             "overall": 90.0, "source": {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64}}]
    f = hub.check_drift(canonical_rows=rows, registry_scores={"r1": 99.0})
    assert any(x["kind"] == "registry-score-as-fact" for x in f)


def test_verified_without_review_flagged():
    rows = [{"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "fp16",
             "overall": 90.0,
             "source": {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64},
             "assurance": "score-reproduced", "platform_review": {"status": "not-reviewed"}}]
    f = hub.check_drift(canonical_rows=rows)
    assert any(x["kind"] == "verified-without-review" for x in f)


def test_duplicate_result_id_detected():
    rows = [
        {"result_id": "dup", "status": "valid", "backend": "vllm", "precision": "fp16",
         "overall": 90.0, "source": {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64}},
        {"result_id": "dup", "status": "valid", "backend": "vllm", "precision": "fp16",
         "overall": 91.0, "source": {"commit": "b" * 40, "source_sha256": "sha256:" + "e" * 64}},
    ]
    f = hub.check_drift(canonical_rows=rows)
    assert any(x["kind"] == "duplicate-result-id" for x in f)


def test_clean_imported_row_has_no_drift():
    rows = [{"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "bf16",
             "overall": 95.88,
             "source": {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64},
             "platform_review": {"status": "not-reviewed"}}]
    assert hub.check_drift(canonical_rows=rows) == []


def test_license_code_and_model_separated():
    # Apache-2.0 code is open-source-software; weights openness is a SEPARATE axis.
    code = {"category": "open-source-software", "spdx": "Apache-2.0"}
    model_open = {"category": "open-weights", "weights_license": "Apache-2.0",
                  "assessment_basis": "weights downloadable under Apache-2.0"}
    validate_artifact("code_license_record", code)
    validate_artifact("model_openness_record", model_open)
    # a restricted model under Apache code is expressible
    hunyuan = {"category": "restricted", "weights_license": "Tencent Hunyuan Community License",
               "assessment_basis": "EU/UK/KR excluded; AUP restrictions",
               "geographic_restrictions": ["EU", "UK", "KR"],
               "acceptable_use_restrictions": ["no disallowed uses per AUP"],
               "attribution_required": True}
    validate_artifact("model_openness_record", hunyuan)
    # unknown must not default to open
    errs = iter_validation_errors("model_openness_record", {"category": "bogus"})
    assert errs


def test_e2e_import_to_renders(tmp_path):
    """End-to-end integration: import -> rebuild canonical -> render the results
    section + the comparison table. The imported score must surface in the results
    section and the model in the table. Exercises the chain the stale-table incident
    broke (regeneration consistency across the two README blocks)."""
    from omnidocbench_rocm import hub, source_import as SI
    from omnidocbench_rocm.registry import render_results_section, generate_registry, render_hub
    import json as _json
    (tmp_path / "legacy").mkdir(parents=True)
    (tmp_path / "legacy" / "canonical_results.legacy.json").write_text(_json.dumps({"results": []}))
    src = SI.build_source(repository="AIwork4me/Demo-ROCm", commit="a" * 40, path="card.json", content="{}")
    ir = {"result_id": "demo-1", "model_id": "demo", "status": "valid", "assurance": "submitted",
          "license_category": "open-weights", "benchmark": {"name": "omnidocbench", "version": "v1.6"},
          "implementation": {"backend": "vllm", "precision": "fp16"},
          "coverage": {"platform": "linux-rocm"}, "metrics": {"overall": 94.2}}
    SI.write_import(tmp_path, SI.build_import(source=src, imported_result=ir, importer_version="0.4.0",
                          imported_at="2026-07-28T00:00:00Z", producer_assurance="submitted"))
    (tmp_path / "registry.yaml").write_text(
        "- model_id: demo\n  name: Demo\n  repo: AIwork4me/Demo-ROCm\n"
        "  license: Apache-2.0\n  license_category: open-weights\n"
        "  platforms:\n    linux-rocm: {badge: community, overall: null}\n", encoding="utf-8")
    doc = hub.rebuild_canonical(tmp_path)
    section = render_results_section(doc["results"], tmp_path / "registry.yaml")
    table = render_hub(generate_registry(tmp_path / "registry.yaml"))
    assert doc["results"][0]["result_id"] == "demo-1" and doc["results"][0]["status"] == "valid"
    assert "94.2" in section              # imported score surfaces in the results section
    assert "Demo-ROCm" in table           # model appears in the comparison table (by repo)


def test_rebuild_canonical_quarantines_legacy_and_keeps_imports(tmp_path):
    """rebuild_canonical = quarantined legacy (valid->superseded) + imports; the
    single deterministic producer of the public canonical store (Round-2 §8/§9)."""
    from omnidocbench_rocm import hub, source_import as SI
    import json as _json
    (tmp_path / "legacy").mkdir(parents=True)
    _row = {"model_id": "m", "platform": "linux-rocm", "backend": "vllm", "precision": "fp16",
            "benchmark": {"name": "omnidocbench", "version": "v1.6"}, "overall": 90.0,
            "assurance": "submitted", "license_category": "open-weights"}
    (tmp_path / "legacy" / "canonical_results.legacy.json").write_text(_json.dumps({"results": [
        {**_row, "result_id": "old", "status": "valid"},          # -> quarantined superseded
        {**_row, "result_id": "ret", "status": "retracted"}]}))   # retained as-is
    src = SI.build_source(repository="AIwork4me/O", commit="a" * 40, path="c.json", content="{}")
    ir = {"result_id": "new", "model_id": "m", "status": "valid", "assurance": "submitted",
          "license_category": "open-weights",
          "benchmark": {"name": "omnidocbench", "version": "v1.6"},
          "implementation": {"backend": "vllm", "precision": "fp16"},
          "coverage": {"platform": "linux-rocm"}, "metrics": {"overall": 95.0}}
    imp = SI.build_import(source=src, imported_result=ir, importer_version="0.4.0",
                          imported_at="2026-07-28T00:00:00Z", producer_assurance="submitted")
    SI.write_import(tmp_path, imp)
    doc = hub.rebuild_canonical(tmp_path)
    statuses = {r["result_id"]: r["status"] for r in doc["results"]}
    assert statuses == {"old": "superseded", "ret": "retracted", "new": "valid"}


def test_generate_hub_is_deterministic(tmp_path):
    from omnidocbench_rocm import source_import as SI
    src = SI.build_source(repository="AIwork4me/O", commit="a" * 40, path="c.json",
                          content="{}", json_pointer="/results/0")
    imp = SI.build_import(source=src, imported_result={"result_id": "r1", "model_id": "m",
                          "status": "valid", "producer_assurance": "submitted",
                          "metrics": {"overall": 90.0},
                          "implementation": {"backend": "vllm", "precision": "fp16"}},
                          importer_version="0.4.0", imported_at="2026-07-28T00:00:00Z",
                          producer_assurance="submitted")
    SI.write_import(tmp_path, imp)
    a = json.dumps(hub.generate_hub(tmp_path), sort_keys=True)
    b = json.dumps(hub.generate_hub(tmp_path), sort_keys=True)
    assert a == b
    doc = hub.generate_hub(tmp_path)
    assert doc["results"][0]["overall"] == 90.0
    assert doc["results"][0]["source"]["commit"] == "a" * 40


def test_registry_score_check_only_applies_to_primary():
    """registry mirrors the PRIMARY per (model,platform); an alternate backend's
    different score is NOT drift (ADR-0016). Only a primary mismatching the
    registry is flagged."""
    from omnidocbench_rocm import hub

    def row(rid, overall, primary=False):
        r = {"result_id": rid, "status": "valid", "model_id": "m", "platform": "linux-rocm",
             "backend": "vllm", "precision": "fp16", "overall": overall,
             "source": {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64}}
        if primary:
            r["primary"] = True
        return r

    rows = [row("m-a", 93.0, primary=True), row("m-b", 91.0)]  # primary + alternate
    # alternate 91.0 != registry 93.0, but alternate is exempt -> NO finding
    f = hub.check_drift(canonical_rows=rows, registry_scores={("m", "linux-rocm"): 93.0})
    assert not any(x["kind"] == "registry-score-as-fact" for x in f), f
    # primary 93.0 != registry 99.0 -> flagged on the primary only
    f2 = hub.check_drift(canonical_rows=rows, registry_scores={("m", "linux-rocm"): 99.0})
    assert any(x["kind"] == "registry-score-as-fact" and x["result_id"] == "m-a" for x in f2)
    assert not any(x["result_id"] == "m-b" for x in f2)


def test_source_assurance_overclaim_flagged_without_review():
    """W1: a row whose retained source_assurance claims a reproduction, with no
    accepted platform_review, is flagged verified-without-review (ADR-0013)."""
    row = {"result_id": "r", "status": "valid", "model_id": "m", "platform": "linux-rocm",
           "backend": "vllm", "precision": "fp16", "overall": 90.0,
           "producer_assurance": "evidence-complete", "assurance": "evidence-complete",
           "source_assurance": "score-reproduced",  # original producer claim, retained
           "source": {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64},
           "platform_review": {"status": "not-reviewed"}}
    f = hub.check_drift(canonical_rows=[row])
    assert any(x["kind"] == "verified-without-review" and "source_assurance" in x["detail"] for x in f), f
    # once reviewed + accepted, the claim is no longer flagged
    row["platform_review"] = {"status": "accepted",
                              "assurance": "score-reproduced",
                              "reviewer": {"id": "r", "type": "human"},
                              "reviewed_at": "2026-07-28T00:00:00Z",
                              "review_artifacts": ["replay.json"]}
    assert not any(x["kind"] == "verified-without-review" for x in hub.check_drift(canonical_rows=[row]))
