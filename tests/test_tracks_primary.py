"""Comparison tracks + primary selection (Round-2 ADR-0016, §13 11-17)."""
import pytest
from omnidocbench_rocm import tracks as T
from omnidocbench_rocm import primary as P


def test_full_and_canary_are_different_tracks():
    full = T.standard_track(subset="full")
    canary = T.standard_track(subset="canary")
    assert full["track_id"] != canary["track_id"]


def test_different_benchmark_version_is_different_track():
    a = T.standard_track(benchmark_version="v1.6")
    b = T.standard_track(benchmark_version="v1.5")
    assert a["track_id"] != b["track_id"]


def test_different_scorer_protocol_is_different_track():
    a = T.standard_track(protocol="default")
    b = T.standard_track(protocol="strict-editdist")
    assert a["track_id"] != b["track_id"]


def test_superseded_hidden_from_default_view():
    tr = T.standard_track()
    valid = {"status": "valid", "benchmark": {"name": "omnidocbench", "version": "v1.6"},
             "comparison_track_id": tr["track_id"]}
    sup = {**valid, "status": "superseded"}
    ret = {**valid, "status": "retracted"}
    view = T.default_view([valid, sup, ret], tr)
    assert [r["status"] for r in view] == ["valid"]


def test_legacy_result_without_track_excluded_from_leaderboard():
    tr = T.standard_track()
    legacy = {"status": "valid", "benchmark": {"name": "omnidocbench", "version": "v1.6"}}
    ok, reason = T.eligible_for_track(legacy, tr)
    assert not ok and "no comparison_track_id" in reason


def test_external_paper_never_enters_rocm_track():
    assert T.is_external_paper({"source": {"kind": "paper"}})
    assert T.is_external_paper({"tags": ["nvidia"]})
    assert not T.is_external_paper({"status": "valid"})


def test_primary_must_resolve_and_be_valid():
    tr = T.standard_track()
    rid = "m-omnidocbench-deadbeef"
    sel = P.make_primary_selection(model_id="m", comparison_track_id=tr["track_id"],
                                   result_id=rid, selected_by="maintainer",
                                   rationale="reference embedded runtime")
    res = [{"result_id": rid, "status": "valid", "comparison_track_id": tr["track_id"]}]
    assert P.validate_selection(sel, results=res, tracks=[tr]) == []


def test_primary_forbids_superseded():
    tr = T.standard_track()
    rid = "m-omnidocbench-deadbeef"
    sel = P.make_primary_selection(model_id="m", comparison_track_id=tr["track_id"],
                                   result_id=rid, selected_by="x", rationale="r")
    res = [{"result_id": rid, "status": "superseded", "comparison_track_id": tr["track_id"]}]
    assert P.validate_selection(sel, results=res, tracks=[tr])


def test_primary_forbids_wrong_track():
    tr = T.standard_track()
    other = T.standard_track(subset="canary")
    rid = "m-omnidocbench-deadbeef"
    sel = P.make_primary_selection(model_id="m", comparison_track_id=tr["track_id"],
                                   result_id=rid, selected_by="x", rationale="r")
    res = [{"result_id": rid, "status": "valid", "comparison_track_id": other["track_id"]}]
    assert P.validate_selection(sel, results=res, tracks=[tr, other])


def test_no_highest_score_auto_primary_exists():
    # There is deliberately no function that picks a primary by score.
    import omnidocbench_rocm.primary as prim_mod
    public = [n for n in dir(prim_mod) if "pick" in n.lower() or "highest" in n.lower()]
    assert public == []


def test_primary_resolution_prefers_round2_record():
    tr = T.standard_track()
    card = {"primary_selection": {"result_id": "new"}, "primary_result_id": "old"}
    assert P.primary_of(card) == "new"
    assert P.primary_of({"primary_result_id": "old"}) == "old"
    assert P.primary_of({}) is None
