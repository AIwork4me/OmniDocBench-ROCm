# ADR-0008: Assurance levels replace the single `verified` badge

- **Status:** Accepted (supersedes the badge-only trust model of ADR-0003; badge policy is updated, not deleted)
- **Date:** 2026-07-27

## Context

The v1 badge collapses a result's trust into one word: `verified`, `community`,
or `community-wanted`. "verified" hides *what* was reproduced — scoring only?
inference? on the same GPU or a different one? A user trusting a "verified"
score cannot tell whether it survived a cross-hardware check or only a scoring
re-run. Worse, a badge is naturally read as a *model-wide* property, inviting
the mistake of propagating one platform's trust to another.

## Decision

Replace the single badge with **per-result assurance levels**, each describing
the specific reproduction depth achieved for THAT result:

| Level | Meaning |
|---|---|
| `submitted` | Result submitted by a contributor; not yet checked. |
| `evidence-complete` | Committed evidence bundle is schema-valid + internally consistent (the old `community` gate). |
| `score-reproduced` | Scoring recomputed from committed predictions in a pinned toolchain within tolerance (the old `verified` scoring-repro gate). |
| `inference-reproduced` | Inference re-run on AMD hardware regenerated predictions (noisy; informational, ADR-0003). |
| `cross-hardware-reproduced` | Reproduced on a *different* AMD GPU/architecture than the origin. |

Invariants (enforced by `assurance.py`):

1. **Assurance is per result** — it lives on each `result_record`.
2. **Assurance never propagates** across results. A model card MUST NOT carry a
   model-wide `assurance`/`badge`/`verified` field (`check_no_propagation`
   rejects it). Model A's score-reproduced says nothing about model B; platform
   X's assurance never leaks to platform Y.
3. **The hub shows the specific assurance** of each result, never a single
   flattened "verified".

The legacy badge is preserved as a *lossy projection* for backward-compat
rendering only (`assurance_from_legacy_badge` / `legacy_badge_from_assurance`):
`score-reproduced`+ → `verified`, `evidence-complete`/`submitted` → `community`.

## Consequences

- A reader sees exactly what was reproduced, per result.
- Per-result independence is structural (the field lives on the record), making
  propagation impossible by construction.
- The `verified` Docker-reproduction path (ADR-0003) maps to
  `score-reproduced`; cross-hardware work earns the stronger level.

## Reversibility

- Reverting restores the badge-only model; the assurance enum and helpers are
  additive. The lossy badge projection already keeps the old hub render working.
