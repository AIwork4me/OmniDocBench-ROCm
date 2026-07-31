# ADR-0013: Immutable source imports + producer/platform review split

- **Status:** Accepted (Round-2 fact-chain spine)
- **Date:** 2026-07-28

## Context

v2 (ADR-0008/0012) put a single per-result `assurance` enum in one place and
called `hub/canonical_results.json` the single source of truth. But the central
file was hand-maintained and held `default/default` stubs no sub-repo ever
produced — the platform was both the *recorder* and the *reviewer* of scores,
with no immutable link back to the sub-repo evidence. Two orthogonal concerns
were conflated: (1) what a model repo **submitted**, and (2) what the central
platform **independently verified**.

## Decision

Establish an **immutable source-import layer** as the only place the central
platform creates an authoritative result, and **split assurance** into two
orthogonal dimensions.

```
model-repo canonical result
   -> hub/imports/<model>/<result>/{source.json, imported-result.json, review.json, meta.json}
        -> generate-hub  ->  hub/canonical_results.json   (DERIVED, never hand-edited)
```

- **`source.json`** — immutable pointer: `repository`, full **40-hex `commit`**
  (no main/master/latest), `path`, `json_pointer`, `source_sha256`
  (`sha256:<64hex>`, recomputed and verified at import).
- **`imported-result.json`** — the source result **verbatim**; the score is
  never mutated on import.
- **`review.json`** — the central `platform_review`; defaults to
  `not-reviewed`; raised only by a separate, evidence-carrying review step.
- **`meta.json`** — the import envelope (`imported_at`, `importer_version`,
  `import_schema_version`, `producer_assurance`) so `load_import` reconstructs a
  complete, schema-valid `import_record` (the three spec files alone lack these).
  Amendment to the original 3-file layout — recorded here so the on-disk contract
  matches the implementation.

Split (enforced in `assurance.py`, schema `$defs platform_review_record` /
`source_reference_record` / `import_record`):

- **producer_assurance** (`submitted` | `evidence-complete`) — owned by the
  sub-repo; copied verbatim on import; the platform never rewrites it.
- **platform_review** (`status` not-reviewed/accepted/rejected/needs-more-evidence
  + `assurance` evidence-accepted/score-reproduced/inference-reproduced/
  cross-hardware-reproduced + reviewer + reviewed_at + review_artifacts) — lives
  **only** on the central imported record, never in a sub-repo card.

Rules (enforced):

1. A legacy v2 `score-reproduced`/`verified` level migrates to
   `producer_assurance=evidence-complete` + `platform_review.status=not-reviewed`
   — no review record exists, so it is **not** promoted (`assurance.producer_assurance_from_legacy`).
2. `platform_review.assurance=score-reproduced` requires a real
   `review_artifact` (the scorer replay); `inference-reproduced` requires real
   GPU evidence; `cross-hardware-reproduced` requires a second hardware's evidence
   (`assurance.validate_platform_review`).
3. Import is **idempotent** (same source → no-op) and **never overwrites** an
   existing import whose source differs (`source_import.write_import` returns
   `conflict`).
4. `generate-hub` reads imports + reviews; `canonical_results.json` becomes
   derived. `check-drift` flags any canonical row with no `source`
   (`missing-source`) or whose score disagrees with its import (`score-mismatch`).

## Consequences

- The platform can no longer invent a `default/default` result; every public
  score traces to an immutable sub-repo commit + sha256.
- Producer claims and platform verification are independently auditable.
- Raising assurance is a deliberate, evidenced act, not an import side-effect.

## Reversibility

- Additive: new `$defs` + `hub/imports/`; existing `canonical_results.json`
  remains readable. The legacy single `assurance` field is retained as a lossy
  projection. Reverting removes the import layer and returns to hand-maintained
  canonical results.
