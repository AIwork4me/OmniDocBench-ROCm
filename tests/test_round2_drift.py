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
