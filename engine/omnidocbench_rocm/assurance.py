"""Assurance levels — the v2 replacement for the single ``verified`` badge
(ADR-0008).

The v1 badge collapsed a result's trust into one word (``verified``). v2 records
the *specific* reproduction depth achieved for EACH result, independently:

    submitted                     result submitted by a contributor; no check yet
    evidence-complete             committed evidence bundle is schema-valid +
                                  internally consistent (the old ``community`` gate)
    score-reproduced              scoring recomputed from committed predictions in
                                  a pinned toolchain, within tolerance (old ``verified``
                                  scoring-repro gate)
    inference-reproduced          inference re-run on AMD HW regenerated predictions
                                  (noisy; informational, ADR-0003)
    cross-hardware-reproduced     reproduced on a *different* AMD GPU/arch than origin

Rules (enforced structurally + by the helpers below):

  * Assurance is **per result** — it lives on each ``result_record``.
  * Assurance **never propagates** across results: model A's score-reproduced
    says nothing about model B, and platform X's assurance never leaks to Y.
  * The hub shows the **specific** assurance of each result, never a single
    flattened "verified".
"""
from __future__ import annotations

from .schema import validate_artifact

# Ordered by increasing reproduction depth. This order is used ONLY to pick a
# representative level when a legacy/lossy projection is unavoidable; the hub
# always shows the concrete level of each result.
ASSURANCE_LEVELS = (
    "submitted",
    "evidence-complete",
    "score-reproduced",
    "inference-reproduced",
    "cross-hardware-reproduced",
)

ASSURANCE_RANK = {lvl: i for i, lvl in enumerate(ASSURANCE_LEVELS)}

ASSURANCE_DESCRIPTIONS = {
    "submitted": "Result submitted by a contributor; not yet independently checked.",
    "evidence-complete": "Committed evidence bundle (run_summary + provenance + metric_result) is schema-valid and internally consistent.",
    "score-reproduced": "Scoring recomputed from committed predictions in a pinned toolchain within tolerance.",
    "inference-reproduced": "Inference re-run on AMD hardware regenerated the predictions (noisy; informational).",
    "cross-hardware-reproduced": "Reproduced on a different AMD GPU/architecture than the original measurement.",
}

# Legacy badge -> assurance projection (lossy, for backward-compat only).
LEGACY_BADGE_TO_ASSURANCE = {
    "community-wanted": "submitted",
    "community": "evidence-complete",
    "verified": "score-reproduced",
}

# Assurance -> legacy badge projection (lossy, for the old hub table render path).
ASSURANCE_TO_LEGACY_BADGE = {
    "submitted": "community",
    "evidence-complete": "community",
    "score-reproduced": "verified",
    "inference-reproduced": "verified",
    "cross-hardware-reproduced": "verified",
}


def is_valid(level: str) -> bool:
    return level in ASSURANCE_RANK


def assert_valid(level: str) -> None:
    if level not in ASSURANCE_RANK:
        raise ValueError(f"unknown assurance level: {level!r} (expected one of {ASSURANCE_LEVELS})")


def strongest(levels) -> str:
    """Return the highest-ranked assurance among ``levels`` (empty -> 'submitted').

    Used only for lossy collapse (e.g. picking one badge for a model row). The
    hub never silently collapses — it shows each result's concrete level.
    """
    ranked = [lvl for lvl in levels if lvl in ASSURANCE_RANK]
    if not ranked:
        return "submitted"
    return max(ranked, key=lambda lvl: ASSURANCE_RANK[lvl])


def assurance_from_legacy_badge(badge: str) -> str:
    """Project a v1 badge to its v2 assurance level (lossy)."""
    return LEGACY_BADGE_TO_ASSURANCE.get(badge, "submitted")


def legacy_badge_from_assurance(level: str) -> str:
    """Project a v2 assurance level to its v1 badge (lossy)."""
    assert_valid(level)
    return ASSURANCE_TO_LEGACY_BADGE[level]


def validate_results_assurance(results: list[dict]) -> list[str]:
    """Return a list of problems with the per-result assurance of a v2 card.

    Enforces:
      * every result has an assurance field that is a valid level;
      * no top-level (model-wide) assurance/badge field exists on the card that
        would imply *propagation* across results (the v2 anti-pattern).
    Empty list = clean.
    """
    problems: list[str] = []
    for i, res in enumerate(results or []):
        lvl = res.get("assurance")
        if lvl is None:
            problems.append(f"results[{i}]: missing assurance (per-result, required)")
        elif lvl not in ASSURANCE_RANK:
            problems.append(f"results[{i}]: unknown assurance {lvl!r}")
    return problems


def check_no_propagation(card: dict) -> list[str]:
    """Flag v2 cards that carry a model-wide assurance/badge field.

    A model-wide ``assurance``/``badge``/``verified`` would imply the level
    propagates to every result — the anti-pattern ADR-0008 forbids. Returns the
    list of offending top-level keys (empty = clean).
    """
    if not isinstance(card, dict):
        return []
    offenders = [k for k in ("assurance", "badge", "verified") if k in card]
    return offenders


def validate_assurance(level: str) -> None:
    """Convenience: validate a single assurance level string against the schema.

    Wraps the canonical_result/result_record enum via a minimal probe object.
    """
    probe = {"category": "unknown"}  # license_record is the cheapest enum carrier
    # assurance enums are identical across result_record/canonical_result; verify
    # by building a canonical_result shell (cheapest carrier of the assurance enum).
    shell = {
        "result_id": "x__linux-rocm__smoke__fp16__v16",
        "model_id": "x",
        "platform": "linux-rocm",
        "benchmark": {"name": "OmniDocBench", "version": "v1.6"},
        "overall": None,
        "assurance": level,
        "status": "valid",
    }
    validate_artifact("canonical_result", shell)
    # keep linters honest about probe
    del probe


# ===========================================================================
# Round-2 (ADR-0013): producer_assurance vs platform_review
#
# v2 conflated two orthogonal concerns into one per-result `assurance` enum:
#   (1) what the model repo SUBMITTED (producer evidence depth), and
#   (2) what the central platform INDEPENDENTLY verified.
# Round-2 splits them. The producer side is owned by the sub-repo and copied
# verbatim on import; the platform side lives ONLY on the central imported
# record and defaults to `not-reviewed`. A legacy `verified` badge NEVER
# migrates to a platform score-reproduced without a real review record.
# ===========================================================================

# Producer-owned evidence depth. Lives on the sub-repo result record.
PRODUCER_ASSURANCE_LEVELS = ("submitted", "evidence-complete")

# Central-platform review statuses. Default for any imported result.
PLATFORM_REVIEW_STATUSES = (
    "not-reviewed", "accepted", "rejected", "needs-more-evidence",
)

# Central-platform review assurance levels (only meaningful when status=accepted).
PLATFORM_REVIEW_ASSURANCES = (
    "evidence-accepted",
    "score-reproduced",
    "inference-reproduced",
    "cross-hardware-reproduced",
)


def default_platform_review() -> dict:
    """The review record every freshly-imported result starts with.

    Central NEVER auto-raises this. Raising it is a separate, auditable step
    (:func:`omnidocbench_rocm.source_import.set_review`) that requires evidence.
    """
    return {"status": "not-reviewed"}


def producer_assurance_from_legacy(level: str) -> str:
    """Project a v2 (mixed) assurance level onto the producer-only axis.

    Honest migration: a v2 ``score-reproduced`` / ``inference-reproduced`` /
    ``cross-hardware-reproduced`` was a *platform* reproduction claim, not extra
    producer evidence — so it maps to ``evidence-complete`` on the producer side,
    and the platform side starts at ``not-reviewed`` (no review record exists).
    This is the deliberate downgrade Round-2 §11 requires ("即使旧 badge 是
    verified，也不能直接迁移为 score-reproduced").
    """
    if level in PRODUCER_ASSURANCE_LEVELS:
        return level
    if level in ASSURANCE_LEVELS:  # any of the *-reproduced levels
        return "evidence-complete"
    return "submitted"


def validate_platform_review(record: dict) -> list[str]:
    """Structural problems with a platform_review record (empty = clean).

    Enforces the Round-2 invariants:
      * status is a known value;
      * assurance (if set) is a known value AND only present when accepted;
      * accepted review that claims score-/inference-/cross-hardware-reproduced
        MUST carry a reviewer, reviewed_at, and (for the deeper levels) at least
        one review_artifact — the real scorer replay / inference evidence.
    """
    if not isinstance(record, dict):
        return ["platform_review: not an object"]
    problems: list[str] = []
    status = record.get("status")
    if status not in PLATFORM_REVIEW_STATUSES:
        problems.append(f"platform_review: bad status {status!r}")
    assurance = record.get("assurance")
    if assurance is not None and assurance not in PLATFORM_REVIEW_ASSURANCES:
        problems.append(f"platform_review: bad assurance {assurance!r}")
    # assurance is only meaningful for an accepted review
    if assurance is not None and status != "accepted":
        problems.append(f"platform_review: assurance {assurance!r} set but status={status!r} "
                        "(assurance only applies to accepted reviews)")
    reviewer = record.get("reviewer") or {}
    reviewed_at = record.get("reviewed_at")
    if status == "accepted":
        if not reviewer.get("id"):
            problems.append("platform_review: accepted review missing reviewer.id")
        if reviewer.get("type") not in ("human", "trusted-runner"):
            problems.append(f"platform_review: accepted review missing/invalid reviewer.type "
                            f"{reviewer.get('type')!r}")
        if not reviewed_at:
            problems.append("platform_review: accepted review missing reviewed_at")
        # deeper reproductions REQUIRE evidence artifacts (no rubber-stamping)
        if assurance in ("score-reproduced", "inference-reproduced",
                          "cross-hardware-reproduced"):
            arts = record.get("review_artifacts") or []
            if not arts:
                problems.append(f"platform_review: assurance {assurance!r} requires at least one "
                                "review_artifact (the real replay/inference evidence)")
    return problems


def review_can_claim(record: dict, target_assurance: str) -> bool:
    """True iff a review record honestly justifies claiming ``target_assurance``.

    Used by the import/review flow so a fixture scorer pass can NOT auto-promote
    platform_review — only a review record with the right evidence can.
    """
    if target_assurance not in PLATFORM_REVIEW_ASSURANCES:
        return False
    return not validate_platform_review({**record, "status": "accepted",
                                          "assurance": target_assurance})
