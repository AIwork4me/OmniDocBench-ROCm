# License / Open-Source Policy

Every model in the Zone carries a normalized **license classification**
(ADR-0010), surfaced on the hub so a commercial user is never misled. This
extends ADR-0006 (which accepted restrictive-open licenses with disclosure) with
a machine-comparable category.

## Categories

| Category | Meaning | Examples |
|---|---|---|
| `open-source-ai` | Open code + weights, permissive, no field-of-use/commercial limits. Strictest bar. | MIT, Apache-2.0 (code+weights) |
| `open-weights` | Weights usable/studied/redistributable/modifiable with at most light AUP — short of the full open-source-ai bar. | many HF "open weights" models |
| `source-available` | Source/weights visible but license is NOT open (non-commercial, no-derivatives, BSL/SSPL). | BSL, SSPL, CC-BY-NC |
| `restricted` | Material restrictions: commercial thresholds, geographic limits, strong AUP. | MinerU OSL, Tencent Hunyuan Community License, Llama-style |
| `closed` | Proprietary — no open access. | vendor models |
| `unknown` | Could not be classified. **Default for missing/ambiguous licenses.** | PDF-Extract-Kit-1.0 (no declared license) |

## Restriction axes

Every `license_record` (and registry row) carries three axes, in addition to
`category` and `spdx`:

- `commercial_use` — free-text summary (e.g. "commercial threshold MAU>100M or
  revenue>$20M", "permitted", "see license").
- `geographic_restrictions` — e.g. "not licensed in EU/UK/KR"; empty when none.
- `acceptable_use_restrictions` — AUP-style usage limits; empty when none.

## Cardinal rule

**Never default a missing or unclear license to `open-source-ai`.** When in
doubt, the category is `unknown` until a human resolves it. The engine enforces
this: `license_class.classify()` returns `unknown` for anything unrecognized, and
`assert_no_default_open_source()` flags an `open-source-ai` claim backed by no
SPDX id or name.

## Where it lives

- `hub/registry.yaml` — `license` + `license_category` + `commercial_use` per row.
- `model_card.json` v2 — `license` (a `license_record`).
- `rocmdoc.yaml` — `licenses.code` / `licenses.weights` (each a `license_record`),
  because code and weights may differ.

```bash
omnidocbench-rocm license-classify "Tencent Hunyuan Community License"
# {"category": "restricted", "commercial_use": "commercial-use conditions; see license", ...}
```
