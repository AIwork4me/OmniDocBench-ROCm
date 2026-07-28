"""Explicit primary-result selection (Round-2 ADR-0016).

v2 had ``primary_result_id`` as a free string on the card. Round-2 makes the
selection a first-class, auditable record and FORBIDS the highest-score
heuristic: a primary is an explicit maintainer choice with a rationale, the
selected result must be ``valid`` and belong to the named comparison track, and
superseded/retracted/invalid results can never be primary.

There is deliberately NO ``pick_primary(results)`` helper that scores — that
function does not exist anywhere in this codebase, by design.
"""
from __future__ import annotations

from datetime import datetime, timezone

POLICY_VERSION = "round-2-2026-07"


def make_primary_selection(*, model_id: str, comparison_track_id: str, result_id: str,
                           selected_by: str, rationale: str,
                           selected_at: str | None = None,
                           policy_version: str = POLICY_VERSION) -> dict:
    """Build a primary_selection record. ``selected_at`` defaults to a supplied
    timestamp; callers in non-deterministic contexts pass it explicitly."""
    return {
        "model_id": model_id,
        "comparison_track_id": comparison_track_id,
        "result_id": result_id,
        "selected_by": selected_by,
        "selected_at": selected_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rationale": rationale,
        "policy_version": policy_version,
    }


def validate_selection(selection: dict, *, results: list[dict],
                       tracks: list[dict] | None = None) -> list[str]:
    """Structural + semantic problems with a primary_selection (empty = clean).

    Checks:
      * schema validity;
      * the chosen result_id exists among the results;
      * the chosen result is ``valid`` (never superseded/retracted/invalid);
      * the chosen result's comparison_track_id matches the selection's track;
      * the track exists in ``tracks`` (when provided).
    """
    from .schema import iter_validation_errors
    problems = [f"primary_selection: {m}"
                for m in iter_validation_errors("primary_selection_record", selection)]
    rid = selection.get("result_id")
    track = selection.get("comparison_track_id")
    by_id = {r.get("result_id"): r for r in (results or [])}
    if rid not in by_id:
        problems.append(f"primary_selection: result_id {rid!r} not found among results")
        return problems
    chosen = by_id[rid]
    if chosen.get("status") != "valid":
        problems.append(f"primary_selection: chosen result {rid!r} status is "
                        f"{chosen.get('status')!r}, not 'valid'")
    chosen_track = chosen.get("comparison_track_id")
    if chosen_track and chosen_track != track:
        problems.append(f"primary_selection: chosen result belongs to track "
                        f"{chosen_track!r}, not the selection's {track!r}")
    if tracks is not None:
        ids = {t.get("track_id") for t in tracks}
        if track not in ids:
            problems.append(f"primary_selection: comparison_track_id {track!r} is not a declared track")
    return problems


def primary_of(card: dict) -> str | None:
    """The explicit primary result_id of a card.

    Resolution order (NEVER by score):
      1. card['primary_selection']['result_id']  (Round-2 record)
      2. card['primary_result_id']               (v2 string, back-compat)
      3. None — and the caller must show ALL valid results, not guess.
    """
    ps = card.get("primary_selection")
    if isinstance(ps, dict) and ps.get("result_id"):
        return ps["result_id"]
    return card.get("primary_result_id")
