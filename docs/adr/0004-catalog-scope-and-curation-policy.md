# ADR-0004: Catalog scope and curation policy

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

ADR-0003 locked the trust bar: a `verified` apex that a maintainer reproduces
in Docker. That gate is O(models × platforms × releases) of maintainer work,
so catalog size directly bounds how much can be `verified`. The Zone is also
an open-source 专区 with contribution infrastructure already built (cookiecutter
template, `docs/contribute-a-model.md`, tiered badges). The open question: is
the catalog a closed curated set, an open leaderboard, or a hybrid — and on
what terms are closed-source / external numbers shown?

## Decision

**Hybrid catalog with a verified anchor.** The hub has three tiers,
hard-separated visually and semantically — no row from a lower tier ever
appears in a higher tier's view:

1. **Flagship comparison** — the homepage headline, `verified`-only. The table
   developers trust for cross-model comparison.
2. **Community tail** — open-source models contributed via the template,
   `community`-badged and self-attested, shown in a secondary "also evaluated"
   section. The ADR-0003 floor (`community` to appear in the table) applies.
3. **External reference** — closed-SOTA numbers from the OmniDocBench paper,
   link-only, clearly labelled external / not-reproduced, never inlined into
   any Zone table and never badged.

The hard separation is the load-bearing decision: it keeps the verified
anchor's trust from leaking into self-attested numbers. A pure open
leaderboard is rejected as structurally infeasible at trust quality here — no
AMD GPU CI (`docs/ci-reality.md`), so "we verify everything" is impossible and
the table would devolve to mostly self-attested scores (the demo-level trust
the Zone exists to replace). A pure closed boutique is rejected because it
wastes the contribution infrastructure and under-delivers on the open-source
positioning.

**Reference set** — the curated flagship models the Zone commits to keeping
`verified` each release. Initial membership: HunyuanOCR, Unlimited-OCR,
MinerU, PaddleOCR-VL, targeted to `verified` on `linux-rocm` first. Membership
follows a **published selection policy**: coverage of the major open
document-parsing architectural families (end-to-end VLM-OCR, pipeline,
lightweight/consumer), one representative per family, runnable on consumer
AMD cards — not personal preference.

**Graduation rule** (community → reference) is published: a model graduates
only at `community` status + sustained demand + maintainer bandwidth to verify
it each release.

**Open-source only (hard line).** Only open-weights + open-code models are
evaluated or listed in any Zone tier. Closed-source models (Gemini, GPT,
mathpix, …) are never evaluated, never inlined, never badged — the
`contribute-a-model.md` Step 1 exclusion stands. Closed SOTA appears solely as
external-reference link-outs.

## Consequences

- The registry renderer (`scripts/generate_registry.py` and the future MkDocs
  site) splits three tiers; the flagship comparison is `verified`-only.
- A selection / graduation policy is required (extends `docs/governance.md` or
  a new `docs/selection-policy.md`).
- Reference-set membership is an ongoing maintainer commitment (Docker
  reproduction each release); graduation is capacity-gated by design.
- The two currently-`community-wanted` reference models (`unlimited-ocr`,
  `hunyuan-ocr`) stay in the incoming lane until `community`, then graduate
  toward `verified`.
- External-reference numbers are not maintained by the Zone (they are the
  paper's); only the link is kept current.

## Reversibility

- The hybrid stance is adjustable (tighten to a boutique, or broaden).
- Reference-set membership is mutable by design via the graduation rule.
- The hardest part to reverse is the published selection / graduation policy
  once contributors plan around it — which is why it is written down rather
  than left implicit.
