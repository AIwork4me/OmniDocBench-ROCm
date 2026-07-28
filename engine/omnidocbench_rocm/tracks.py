"""Comparison Tracks (Round-2 ADR-0016).

A track is the set of comparison conditions (benchmark + dataset subset + scorer
protocol + eligibility). Results are compared ONLY within a track. The v2 model
let a full-set result sit next to a canary result next to a paper number and
implied they were comparable — they are not.

Track identity is derived deterministically:

    track_id = "<benchmark>-v<version>-<subset>-<protocol>"

Rules (Round-2 §3.4):

  * full vs canary => different tracks.
  * different benchmark version => different tracks.
  * different scorer protocol => different tracks.
  * layout-only / table-only / full-document => different tracks.
  * external paper results NEVER enter a ROCm track.
  * superseded/retracted/invalid are excluded from the DEFAULT view of a track
    (history is retained, never deleted).
  * track content changes yield a new track_id or a version bump.

Pure module (no I/O).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

# Statuses excluded from a track's DEFAULT (public) comparison view. They are
# still retained for history — never physically deleted (Round-2 §3.7).
HIDDEN_STATUS = ("superseded", "retracted", "invalid")


def _slug(value: Any) -> str:
    s = "".join(c if c.isalnum() else "-" for c in str(value).lower()).strip("-")
    return s or "x"


def make_track_id(*, benchmark_id: str, benchmark_version: str,
                  dataset_subset: str = "full", scorer_protocol: str = "default",
                  extra: str = "") -> str:
    """Deterministic track id.

    The ``extra`` token (e.g. ``layout-only`` / ``table-only``) lets
    sub-scope tracks coexist; the scorer_revision is folded into the id only via
    the protocol token so the id stays human-readable while still changing when
    the protocol changes.
    """
    parts = [_slug(benchmark_id), _slug(benchmark_version),
             _slug(dataset_subset), _slug(scorer_protocol)]
    if extra:
        parts.append(_slug(extra))
    base = "-".join(parts)
    # A short disambiguating suffix derived from the full track definition makes
    # the id change if the *contents* (e.g. page_set_hash) change even when the
    # human tokens collide — deterministic, never random.
    canon = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    suffix = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}"


def validate_track(track: dict) -> list[str]:
    """Structural problems with a comparison_track_record (empty = clean)."""
    from .schema import iter_validation_errors
    problems = [f"track: {m}" for m in iter_validation_errors("comparison_track_record", track)]
    bench = track.get("benchmark") or {}
    if not bench.get("id"):
        problems.append("track: benchmark.id is required")
    elig = track.get("eligibility") or {}
    excl = elig.get("excluded_statuses")
    if excl is not None:
        bad = [s for s in excl if s not in ("valid", "superseded", "retracted", "invalid")]
        if bad:
            problems.append(f"track: eligibility.excluded_statuses has unknown status(es) {bad!r}")
    return problems


def eligible_for_track(result: dict, track: dict) -> tuple[bool, str | None]:
    """Is ``result`` eligible for the DEFAULT view of ``track``?

    Returns ``(eligible, reason)``. A result is excluded when:
      * its status is in the track's excluded_statuses (default: the hidden set);
      * its benchmark id/version does not match the track;
      * it carries no comparison_track_id at all (legacy result — §3.4 req 5);
      * its own comparison_track_id differs from the track's id.
    """
    status = result.get("status", "valid")
    elig = track.get("eligibility") or {}
    excluded = tuple(elig.get("excluded_statuses") or HIDDEN_STATUS)
    if status in excluded:
        return False, f"status {status!r} excluded from default view"
    bench = result.get("benchmark") or {}
    tbench = track.get("benchmark") or {}
    # benchmark id (track) vs display name (result) are the same benchmark up to
    # case/slug ("omnidocbench" id == "OmniDocBench" display name) — compare loosely.
    if tbench.get("id") and bench.get("name") and str(bench.get("name")).lower() != str(tbench.get("id")).lower():
        return False, f"benchmark {bench.get('name')!r} != track {tbench.get('id')!r}"
    if tbench.get("version") and bench.get("version") and bench.get("version") != tbench.get("version"):
        return False, f"benchmark version {bench.get('version')!r} != track {tbench.get('version')!r}"
    rid_track = result.get("comparison_track_id")
    tid = track.get("track_id")
    if not rid_track:
        return False, "result has no comparison_track_id (legacy result; not in default leaderboard)"
    if tid and rid_track != tid:
        return False, f"result track {rid_track!r} != {tid!r}"
    return True, None


def default_view(results: list[dict], track: dict) -> list[dict]:
    """The results eligible for the DEFAULT (public) comparison view of a track."""
    return [r for r in (results or []) if eligible_for_track(r, track)[0]]


def is_external_paper(result: dict) -> bool:
    """Heuristic: a result sourced from a paper / upstream / non-ROCm run.

    External results may be recorded as CONTEXT on a track but never ENTER a
    ROCm comparison track (Round-2 §3.4 req 6).
    """
    src = (result.get("source") or {})
    if isinstance(src, dict) and src.get("kind") in ("paper", "upstream", "vendor"):
        return True
    tags = result.get("tags") or []
    return any(t in ("paper", "external", "nvidia", "tensorrt", "upstream-official")
               for t in tags)


def standard_track(*, benchmark_id: str = "omnidocbench", benchmark_version: str = "v1.6",
                   subset: str = "full", protocol: str = "default",
                   scorer_revision: str = "", page_set_hash: str = "",
                   extra: str = "") -> dict:
    """Build a canonical track record with the standard eligibility defaults."""
    tid = make_track_id(benchmark_id=benchmark_id, benchmark_version=benchmark_version,
                        dataset_subset=subset, scorer_protocol=protocol, extra=extra)
    return {
        "track_id": tid,
        "version": "1",
        "benchmark": {"id": benchmark_id, "version": benchmark_version},
        "dataset": {"subset": subset, "page_set_hash": page_set_hash},
        "scorer": {"protocol": protocol, "revision": scorer_revision},
        "eligibility": {
            "excluded_statuses": list(HIDDEN_STATUS),
        },
    }
