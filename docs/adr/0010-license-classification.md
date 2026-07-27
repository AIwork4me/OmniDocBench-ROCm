# ADR-0010: License / open-source classification

- **Status:** Accepted (extends ADR-0006's licensing posture; does not weaken it)
- **Date:** 2026-07-27

## Context

ADR-0006 accepted restrictive-open licenses (MinerU OSL, Tencent Hunyuan) into
the catalog and required `license` + `commercial_use` disclosure. But "license:
Apache-2.0" vs. "license: MinerU Open Source License" is not machine-comparable,
and the absence of a license field was silently treated as acceptable. A
commercial user needs a normalized category, and the project must never *imply*
a model is open when its license is unclear.

## Decision

Add a six-category classification (`license_class.py`, `$def license_record`):

| Category | Meaning |
|---|---|
| `open-source-ai` | Meets an open-source definition for AI (open code + weights, permissive, no field-of-use/commercial limits). Strictest bar. |
| `open-weights` | Weights usable/studied/redistributable/modifiable with at most light AUP — short of the full open-source-ai bar. |
| `source-available` | Source/weights visible but license is NOT open (non-commercial, no-derivatives, BSL/SSPL). |
| `restricted` | Available with material restrictions: commercial thresholds, geographic limits, strong AUP (MinerU OSL, Hunyuan, Llama-style). |
| `closed` | Proprietary — no open access. |
| `unknown` | Could not be classified. **The default for any missing/ambiguous license.** |

Each `license_record` carries three restriction axes — `commercial_use`,
`geographic_restrictions`, `acceptable_use_restrictions` — so a commercial user
is never misled (mirroring HuggingFace's restrictive-license labelling).

**Cardinal rule (enforced):** never default a missing/unclear license to
`open-source-ai`. `classify()` returns `unknown` for anything unrecognized;
`assert_no_default_open_source` flags an `open-source-ai` claim with no SPDX id
or name backing it. A maintainer may still set a category deliberately, but the
unsafe *default* is blocked.

## Consequences

- Every entry has a comparable, normalized category rendered on the hub.
- Restrictive models are visibly flagged; unknown is honest, not silently open.
- `commercial_use` carries forward from ADR-0006; the two new axes add geographic
  and acceptable-use disclosure.

## Reversibility

- The category is a derived label over the existing `license` string; tightening
  or loosening the known-license table is a one-file change.
