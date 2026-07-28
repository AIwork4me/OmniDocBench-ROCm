# ADR-0019: Legacy badge + registry-score retirement

- **Status:** Accepted (Round-2 deprecation)
- **Date:** 2026-07-28

## Context

Pre-v2/v2 carried several redundant trust signals that Round-2 retires: the v1
`badge` (`verified`/`community`/`community-wanted`), `hub/registry.yaml`
hand-maintained `overall` scores, hand-written README result tables, and the
"highest badge implies model status" derivation. These were independent fact
sources that drifted.

## Decision

Retire them **gradually**, not by deletion:

1. `hub/registry.yaml` keeps only **discovery metadata** (model identity,
   repository, lifecycle, maintainers, source locations). Scores and assurance
   come **only** from imported canonical results + platform reviews (ADR-0013).
2. New code **stops reading** legacy `score`/`badge` as fact; the old fields are
   accepted only as compat input.
3. The README results block is generated from `canonical_results.json` (ADR-0012)
   and `--check` fails on drift.
4. CI (`check-drift`) flags `registry-score-as-fact` and
   `verified-without-review` findings so the old signals are not silently
   re-introduced.
5. A v1 `verified` badge **does not** migrate to `platform_review` — it becomes
   `producer_assurance=evidence-complete` + `platform_review.status=not-reviewed`
   (ADR-0013).

## Consequences

- One fact chain; old signals are compat-only and drift is machine-caught.
- No "verified-by-badge" trust inflation.

## Reversibility

- No historical result is deleted; statuses (`valid`/`superseded`/`retracted`/
  `invalid`) are the only lifecycle transitions. Legacy readers remain.
