# ADR-0014: License classification — code vs model openness

- **Status:** Accepted (Round-2 correctness fix)
- **Date:** 2026-07-28

## Context

The v2 `license_record.category` enum (`open-source-ai | open-weights |
source-available | restricted | closed | unknown`) was applied to a model card's
single `license` field. Apache-2.0 **code** was routinely classified as
`open-source-ai`, but Apache-2.0 code says nothing about the **weights** — many
"open-source-ai" labels were wrong (weights were merely downloadable under a
restrictive license). ADR-0010's category taxonomy is the **model-openness**
axis; it was being conflated with the code-license axis.

## Decision

Split license declaration into two orthogonal records (schema `$defs
code_license_record` + `model_openness_record`; `model_card_v2.licenses =
{code, model}`):

- **code** — software license: `category`
  (`open-source-software | proprietary | unknown`), `spdx`, `url`.
- **model** — weights openness: `category` (the ADR-0010 enum),
  `weights_license`, `assessment_basis`, `commercial_use`,
  `geographic_restrictions[]`, `acceptable_use_restrictions[]`,
  `attribution_required`, `url`.

Rules (enforced):

1. Code license does **not** imply weights openness; weights being downloadable
   does **not** imply `open-source-ai`.
2. When uncertain, `category=unknown` **with** an `assessment_basis` — never
   default an unknown to an "open" category.
3. Special licenses are expressed accurately: e.g. Tencent Hunyuan Community
   License → `model.category=restricted` (or `source-available`) with EU/UK/KR
   `geographic_restrictions` + AUP `acceptable_use_restrictions` +
   `attribution_required`.
4. The Hub renders code license and model openness **separately**.
5. The legacy single `license` field is retained as a back-compat projection.

## Consequences

- Hunyuan/MinerU-style special licenses are no longer mislabeled "open-source-ai".
- `unknown` is a first-class, honest state, not a silent default-to-open.

## Reversibility

- Additive `$defs` + optional `licenses` on `model_card_v2`; the legacy
  `license` field still validates. Reverting drops the split.
