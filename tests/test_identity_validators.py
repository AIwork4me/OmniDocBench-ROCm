"""Identity validators (Round-2 P0-5 / P0-6): unknown-assurance-ceiling and
primary-uniqueness-per-track. These DETECT violations via ``check_drift``; they
do NOT auto-downgrade producer_assurance or auto-demote primaries — those are
maintainer value-decisions (the validators make the fact loop visible instead).
"""
from omnidocbench_rocm import hub
from omnidocbench_rocm import run_spec as rs


def _spec_unknown():
    return {"model": {"model_revision": "unknown", "weights_sha256": "unknown"},
            "benchmark": {"page_set_hash": "unknown"},
            "inference": {"prompt_hash": "unknown", "preprocessing_config_hash": "unknown",
                          "postprocessing_config_hash": "unknown", "runtime_config_hash": "unknown"}}


def _spec_pinned():
    return {"model": {"model_revision": "abc123", "weights_sha256": "sha256:w"},
            "benchmark": {"page_set_hash": "sha256:p"},
            "inference": {"prompt_hash": "sha256:1", "preprocessing_config_hash": "sha256:2",
                          "postprocessing_config_hash": "sha256:3", "runtime_config_hash": "sha256:4"}}


def _src():
    return {"commit": "a" * 40, "source_sha256": "sha256:" + "f" * 64}


# --- run_spec.unknown_reproduction_critical ---------------------------------

def test_unknown_reproduction_critical_lists_all_unknowns():
    assert set(rs.unknown_reproduction_critical(_spec_unknown())) == set(rs.REPRODUCTION_CRITICAL_FIELDS)


def test_unknown_reproduction_critical_empty_when_pinned():
    assert rs.unknown_reproduction_critical(_spec_pinned()) == []


def test_unknown_reproduction_critical_partial():
    spec = _spec_pinned()
    spec["benchmark"]["page_set_hash"] = "unknown"  # only one reverts to unknown
    assert rs.unknown_reproduction_critical(spec) == ["benchmark.page_set_hash"]


# --- unknown-identity assurance ceiling (P0-5) ------------------------------

def test_ceiling_flags_evidence_complete_with_unknown_identity():
    row = {"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "bf16",
           "producer_assurance": "evidence-complete", "source": _src()}
    imp = {"imported_result": {"result_id": "r1", "producer_assurance": "evidence-complete",
                               "run_spec": _spec_unknown()}}
    f = hub.check_drift(canonical_rows=[row], imports=[imp])
    assert any(x["kind"] == "unknown-identity-assurance-ceiling" for x in f), f


def test_ceiling_does_not_flag_submitted():
    # submitted + unknown identity is HONEST (no overclaim) -> not flagged.
    row = {"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "bf16",
           "producer_assurance": "submitted", "source": _src()}
    imp = {"imported_result": {"result_id": "r1", "producer_assurance": "submitted",
                               "run_spec": _spec_unknown()}}
    f = hub.check_drift(canonical_rows=[row], imports=[imp])
    assert not any(x["kind"] == "unknown-identity-assurance-ceiling" for x in f), f


def test_ceiling_clean_when_identity_pinned():
    row = {"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "bf16",
           "producer_assurance": "evidence-complete", "source": _src()}
    imp = {"imported_result": {"result_id": "r1", "producer_assurance": "evidence-complete",
                               "run_spec": _spec_pinned()}}
    f = hub.check_drift(canonical_rows=[row], imports=[imp])
    assert not any(x["kind"] == "unknown-identity-assurance-ceiling" for x in f), f


def test_ceiling_inert_without_imports():
    # check_drift called without imports (legacy/minimal fixtures) must not
    # fabricate ceiling findings it cannot substantiate.
    row = {"result_id": "r1", "status": "valid", "backend": "vllm", "precision": "bf16",
           "producer_assurance": "evidence-complete", "source": _src()}
    f = hub.check_drift(canonical_rows=[row])
    assert not any(x["kind"] == "unknown-identity-assurance-ceiling" for x in f), f


# --- primary-uniqueness per (model, track) (P0-6 / Standard §7.3) -----------

def _prow(rid, primary=False, track="omnidocbench-v1-6-full-default-f23c37da", model="m",
          platform="linux-rocm"):
    r = {"result_id": rid, "status": "valid", "model_id": model, "backend": "vllm",
         "precision": "bf16", "platform": platform, "comparison_track_id": track, "source": _src()}
    if primary:
        r["primary"] = True
    return r


def test_two_primaries_same_model_platform_track_flagged():
    # the real ambiguity: 2 primaries on the SAME (model, platform, track)
    rows = [_prow("m-linux", primary=True), _prow("m-win", primary=True)]  # both default linux-rocm
    f = hub.check_drift(canonical_rows=rows)
    assert any(x["kind"] == "multiple-primaries-per-track" for x in f), f


def test_two_primaries_same_track_different_platform_ok():
    # ADR-0021: one primary per platform on the same track is legitimate (e.g. mineru2.5
    # linux vlm-vllm + windows vlm-llamacpp on the full track) — NOT flagged.
    rows = [_prow("m-linux", primary=True, platform="linux-rocm"),
            _prow("m-win", primary=True, platform="windows-hip")]
    f = hub.check_drift(canonical_rows=rows)
    assert not any(x["kind"] == "multiple-primaries-per-track" for x in f), f


def test_one_primary_per_model_track_ok():
    rows = [_prow("m-linux", primary=True), _prow("m-win")]
    f = hub.check_drift(canonical_rows=rows)
    assert not any(x["kind"] == "multiple-primaries-per-track" for x in f), f


def test_two_primaries_on_different_tracks_ok():
    rows = [_prow("m-a", primary=True, track="track-1"), _prow("m-b", primary=True, track="track-2")]
    f = hub.check_drift(canonical_rows=rows)
    assert not any(x["kind"] == "multiple-primaries-per-track" for x in f), f


# --- pipeline backend must be its own model_id (ADR-0017) -------------------

def _vrow(rid, model="m", backend="vllm",
          track="omnidocbench-v1-6-full-default-f23c37da", lic="open-source-ai"):
    return {"result_id": rid, "status": "valid", "model_id": model, "backend": backend,
            "precision": "bf16", "platform": "linux-rocm", "license_category": lic,
            "comparison_track_id": track, "source": _src()}


def test_pipeline_and_vlm_same_model_id_flagged():
    # a VLM model_id carrying a pipeline-backend VALID result alongside VLM results
    # is mis-filing the pipeline (e.g. mineru2.5 + 86.x pipeline). ADR-0017.
    rows = [_vrow("m-vlm", backend="vlm-vllm"), _vrow("m-pipe", backend="pipeline")]
    f = hub.check_drift(canonical_rows=rows)
    assert any(x["kind"] == "pipeline-and-vlm-same-model-id" for x in f), f


def test_pipeline_only_model_id_ok():
    # a model_id whose VALID results are ALL pipeline-type is fine (e.g. a future
    # pipeline-tool model). Not flagged.
    rows = [_vrow("p1", backend="pipeline")]
    f = hub.check_drift(canonical_rows=rows)
    assert not any(x["kind"] == "pipeline-and-vlm-same-model-id" for x in f), f


def test_vlm_only_model_id_ok():
    rows = [_vrow("v1", backend="vllm")]
    f = hub.check_drift(canonical_rows=rows)
    assert not any(x["kind"] == "pipeline-and-vlm-same-model-id" for x in f), f


# --- canary / sample-track result must not be valid (§7) --------------------

def test_canary_track_valid_flagged():
    rows = [_vrow("c1", track="omnidocbench-v1-6-canary-default-11666b79")]
    f = hub.check_drift(canonical_rows=rows)
    assert any(x["kind"] == "canary-track-result-valid" for x in f), f


def test_full_track_valid_ok():
    rows = [_vrow("f1", track="omnidocbench-v1-6-full-default-f23c37da")]
    f = hub.check_drift(canonical_rows=rows)
    assert not any(x["kind"] == "canary-track-result-valid" for x in f), f


# --- license_category drift between registry and canonical (§6) -------------

def test_license_category_drift_flagged():
    rows = [_vrow("l1", lic="open-weights")]
    reg = [{"model_id": "m", "license_category": "open-source-ai"}]
    f = hub.check_drift(canonical_rows=rows, registry_rows=reg)
    assert any(x["kind"] == "license-category-drift" for x in f), f


def test_license_category_agrees_ok():
    rows = [_vrow("l1", lic="open-source-ai")]
    reg = [{"model_id": "m", "license_category": "open-source-ai"}]
    f = hub.check_drift(canonical_rows=rows, registry_rows=reg)
    assert not any(x["kind"] == "license-category-drift" for x in f), f


def test_license_drift_inert_without_registry_rows():
    rows = [_vrow("l1", lic="open-weights")]
    f = hub.check_drift(canonical_rows=rows)  # no registry_rows -> inert
    assert not any(x["kind"] == "license-category-drift" for x in f), f


def test_license_unknown_not_treated_as_drift():
    rows = [_vrow("l1", lic="unknown")]
    reg = [{"model_id": "m", "license_category": "open-source-ai"}]
    f = hub.check_drift(canonical_rows=rows, registry_rows=reg)
    assert not any(x["kind"] == "license-category-drift" for x in f), f
