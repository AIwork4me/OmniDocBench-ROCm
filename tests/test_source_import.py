"""Immutable source-import layer (Round-2 ADR-0013, §13 1-6, 8-9)."""
import json
import pytest
from omnidocbench_rocm import source_import as SI
from omnidocbench_rocm import assurance as A


COMMIT = "8511898432e7bb58821f2c85751157a438d56c2e"


def _card_text(overall=95.88):
    return json.dumps({"results": [{"result_id": "ovisocr2-omnidocbench-abc",
        "model_id": "ovisocr2", "status": "valid", "producer_assurance": "submitted",
        "metrics": {"overall": overall},
        "implementation": {"backend": "vllm", "precision": "bf16"}}]})


def _import(overall=95.88, content=None):
    text = content if content is not None else _card_text(overall)
    src = SI.build_source(repository="AIwork4me/OvisOCR2-ROCm", commit=COMMIT,
                          path="model_card_v2.json", content=text, json_pointer="/results/0")
    ir = {"result_id": "ovisocr2-omnidocbench-abc", "model_id": "ovisocr2", "status": "valid",
          "producer_assurance": "submitted", "metrics": {"overall": overall},
          "implementation": {"backend": "vllm", "precision": "bf16"}}
    return SI.build_import(source=src, imported_result=ir, importer_version="0.4.0",
                           imported_at="2026-07-28T00:00:00Z",
                           producer_assurance=SI.derive_producer_assurance(ir)), text


def test_source_sha256_recomputed_and_verified():
    imp, text = _import()
    assert SI.validate_import(imp, source_content=text) == []


def test_immutable_commit_required():
    assert SI.is_immutable_commit(COMMIT)
    for bad in ("main", "master", "latest", "HEAD", "8511898", "g" * 40):
        assert not SI.is_immutable_commit(bad), bad


def test_changed_source_is_detected():
    imp, text = _import()
    problems = SI.validate_import(imp, source_content=text.replace("95.88", "99.99"))
    assert any("source CHANGED" in p or "does not match" in p for p in problems)


def test_floating_commit_rejected():
    imp, text = _import()
    bad = json.loads(json.dumps(imp))
    bad["source"]["commit"] = "main"
    assert any("40-hex immutable SHA" in p for p in SI.validate_import(bad, source_content=text))


def test_producer_assurance_preserved_not_mutated():
    imp, text = _import()
    assert SI.validate_import(imp, source_content=text) == []
    bad = json.loads(json.dumps(imp))
    bad["producer_assurance"] = "evidence-complete"  # platform must not rewrite producer
    probs = SI.validate_import(bad, source_content=text)
    assert any("producer_assurance mutated" in p for p in probs)


def test_platform_review_defaults_not_reviewed():
    imp, _ = _import()
    assert imp["platform_review"]["status"] == "not-reviewed"


def test_legacy_verified_does_not_auto_promote():
    # a v2 result carrying assurance=score-reproduced imports as evidence-complete
    # producer + not-reviewed platform (no review record exists).
    ir = {"result_id": "x", "model_id": "m", "status": "valid",
          "assurance": "score-reproduced", "metrics": {"overall": 90.0},
          "implementation": {"backend": "vllm", "precision": "fp16"}}
    assert SI.derive_producer_assurance(ir) == "evidence-complete"


def test_write_import_idempotent(tmp_path):
    imp, _ = _import()
    r1 = SI.write_import(tmp_path, imp)
    r2 = SI.write_import(tmp_path, imp)
    assert r1["status"] == "created" and r2["status"] == "idempotent"


def test_write_import_refuses_overwrite_on_changed_source(tmp_path):
    imp, text = _import()
    SI.write_import(tmp_path, imp)
    # same result-id, DIFFERENT source sha -> conflict, never overwritten
    src2 = SI.build_source(repository="AIwork4me/OvisOCR2-ROCm", commit=COMMIT,
                           path="model_card_v2.json", content=text + " ")
    imp2 = json.loads(json.dumps(imp)); imp2["source"] = src2
    r = SI.write_import(tmp_path, imp2)
    assert r["status"] == "conflict"
    # the original source.json is untouched
    rec = SI.load_import(tmp_path, "ovisocr2", "ovisocr2-omnidocbench-abc")
    assert rec["source"]["source_sha256"] == imp["source"]["source_sha256"]


def test_load_round_trip(tmp_path):
    imp, _ = _import()
    SI.write_import(tmp_path, imp)
    rec = SI.load_import(tmp_path, "ovisocr2", "ovisocr2-omnidocbench-abc")
    assert rec is not None
    assert rec["imported_result"]["metrics"]["overall"] == 95.88
    assert rec["platform_review"]["status"] == "not-reviewed"


def test_set_review_requires_evidence(tmp_path):
    imp, _ = _import()
    SI.write_import(tmp_path, imp)
    # score-reproduced without an artifact -> rejected
    bad_review = {"status": "accepted", "assurance": "score-reproduced",
                  "reviewer": {"id": "r", "type": "human"},
                  "reviewed_at": "2026-07-28T00:00:00Z"}
    assert SI.set_review(tmp_path, "ovisocr2", "ovisocr2-omnidocbench-abc", bad_review)
    # with a real replay artifact -> accepted
    good_review = {**bad_review, "review_artifacts": ["hub/runs/scorer-replay.json"]}
    assert SI.set_review(tmp_path, "ovisocr2", "ovisocr2-omnidocbench-abc", good_review) == []


def test_public_row_carries_source_and_split_assurance(tmp_path):
    imp, _ = _import()
    row = SI.to_public_row(imp)
    assert row["source"]["commit"] == COMMIT
    assert row["producer_assurance"] == "submitted"
    assert row["platform_review"]["status"] == "not-reviewed"
    assert row["overall"] == 95.88
