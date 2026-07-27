# ADR-0007: Model Card v2 and result records

- **Status:** Accepted (supersedes the v1 `model_card` shape in artifact-schema.json; v1 remains valid for backward compatibility)
- **Date:** 2026-07-27

## Context

The v1 `model_card.json` (schema_version 1) carries a *single* `overall` plus a
per-platform `badge` object. That conflates several distinct things:

- a model's *identity* (model_id, version, license),
- its *supported platforms* (the `platforms` array), and
- one or more *measured results* (overall + submetrics) — but only one overall
  even when two platforms were measured.

When a model is measured under two combinations (e.g. linux-rocm/vLLM/fp16 and
windows-hip/llama.cpp/fp16), v1 cannot represent both scores honestly; the
single `overall` gets ambiguously attributed. The badge is also a *trust* claim
collapsed into one word, addressed in ADR-0008.

## Decision

Introduce **Model Card v2** (`schema_version: 2`, `$def model_card_v2` in
artifact-schema.json). A v2 card holds:

- model identity (`model_id`, `model_version`, optional `license`, `upstream`),
- a `results[]` array of **result records**, where each result record is exactly
  ONE combination of **platform + backend + precision + benchmark** with its own
  `status`, `assurance`, `metrics`, `implementation`, `coverage`, `hardware`,
  `software`, `artifacts`, and `provenance`.

Key invariants (enforced by `model_card_v2.validate_card_v2`):

1. **`result_id` is unique and reproducible.** It is a deterministic slug of the
   (model, platform, backend, precision, benchmark) tuple plus a 12-hex sha256
   suffix — same tuple always yields the same id; different tuples never collide.
2. **`platforms` is derived** from the results' `coverage.platform`, never
   hand-written. If present in the file it must equal the derivation.
3. **Retracted / invalid / superseded records are retained, never deleted.** They
   carry their `status` and are hidden from generated public lists (ADR-0012) but
   remain in the card for audit.
4. **`metrics` is extensible** (`additionalProperties: true`) so new metrics do
   not require a schema bump; only `overall` is required (nullable).
5. **`primary_result_id` is an explicit choice**, never auto-assigned to the
   highest score (ADR-0012 § "no auto-primary").
6. All timestamps are RFC3339 (`format: date-time`, enforced); all hashes are
   `sha256:<64hex>` (pattern-enforced).

Provenance *completeness* (created_at_utc, git_commit, dataset hashes) is NOT a
base-schema constraint — it is a *depth* concern enforced by the conformance
profiles (ADR-0011). This keeps legacy-card migration structurally valid while
profiles enforce completeness.

## v1 → v2 migration

`omnidocbench-rocm migrate-model-card input.json` (module `migrate.py`) maps v1
fields forward **without guessing**: only fields with a clear v1 source are
carried; unknowns (git_commit, dataset hashes, precision, page_count) are left
absent and listed in the machine-readable report. The single v1 `overall` is
projected onto the primary platform (highest badge; first on tie) — a
*deterministic projection*, flagged in the report, not a fabrication. Migration
is **idempotent** (`migrate(migrate(x)) == migrate(x)`).

## Consequences

- v1 cards remain readable/valid (backward compatible); the v1 `$def` is kept.
- A model with N measured combinations now carries N honest result records.
- result_id is the stable join key between cards, the canonical results store
  (ADR-0012), and the hub.

## Reversibility

- v2 is additive; reverting means dropping the `model_card_v2`/`result_record`
  `$defs` and the migration tool. v1 data is untouched throughout.
