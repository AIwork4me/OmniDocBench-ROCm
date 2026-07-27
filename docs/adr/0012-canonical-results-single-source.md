# ADR-0012: Canonical results — single source of truth

- **Status:** Accepted (establishes the data-flow spine for the hub + README)
- **Date:** 2026-07-27

## Context

Scores previously appeared in three independent places: each per-model
`model_card.json`, `hub/registry.yaml`'s `platforms.overall`, and hand-written
README tables. They could (and did) drift. The README also implied a single
"primary" result by listing one row per model, with no rule for *which*
combination that represented — inviting the silent "highest score wins" mistake.

## Decision

Establish **one** data flow with a single source of truth:

```
hub/canonical_results.json   (the ONLY place scores live)
        -> README generated-results section    (derived, never hand-written)
        -> hub comparison table                (registry.yaml mirror, drift-checked)
```

- `hub/canonical_results.json` is a list of `canonical_result` entries (one per
  measured combination). It is the source of truth for `overall`, `assurance`,
  `status`, and `license_category`.
- `python -m omnidocbench_rocm.registry generate` regenerates the README section
  delimited by `<!-- BEGIN GENERATED RESULTS -->` / `<!-- END GENERATED RESULTS -->`.
  Output is **deterministic** (sorted by model_id, platform, result_id).
- `python -m omnidocbench_rocm.registry generate --check` **fails on any diff**:
  README section drift, registry.yaml `overall` != canonical, or a measured
  registry platform with no canonical entry. canonical_results.json is the
  authority; registry.yaml is a checked mirror.

Rules (enforced):

1. **Scores live only in canonical_results.json.** README/Hub never hand-write a
   score.
2. **No auto-primary.** The primary result is an explicit `primary` /
   `primary_result_id` choice — never the highest score. The generated table
   lists every valid result; it does not collapse to a "best".
3. **Retracted/invalid results are hidden from the public list but retained**
   (never deleted); a footer notes how many are hidden.
4. **result_id is the join key** to model cards (ADR-0007) and the manifest.

## Consequences

- One edit point for scores; drift is machine-caught in CI.
- No silent "highest-as-primary"; every measured combination is visible.
- Retractions are auditable, not erased.

## Reversibility

- canonical_results.json is additive. Reverting means the README section returns
  to hand-maintenance and the drift check is removed; registry.yaml is unchanged.
