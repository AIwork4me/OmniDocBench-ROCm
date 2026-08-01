# Central ledger audit — Phase 0 (2026-08-01)

Detectors-first ledger close for `feat/rocmdoc-1.0-governance`. Read-only audit →
detectors (Commit ①) → data fixes (Commit ②). All changes enacted on the
immutable import store + derived canonical; `canonical_results.json` regenerated
via `scripts/regen_hub.py` (never hand-edited).

## Before → after (5 P0 defects)

| # | Defect | Before (HEAD 607683a) | After | Status |
|---|---|---|---|---|
| 1 | MinerU pipeline under VLM model_id | `86.48`/`86.59` valid under `mineru2.5` | re-filed under **`mineru-pipeline`** (primary); `mineru2.5` VLM-only (ADR-0017) | resolved |
| 2 | Unlimited 22.3 on leaderboard | canary-track, `status=valid`, visible | `status=invalid` (hidden; retained as history) | resolved |
| 5 | license_category drift (4 models) | registry `open-source-ai`/`restricted` ≠ canonical `open-weights`/`source-available` | unified from each model repo `model_card_v2` code+model roll-up (Apache→`open-source-ai`, MinerU commercial-threshold→`restricted`) | resolved |
| 3 | PaddleOCR-VL 1.6 Linux result | no valid Linux ROCm result (only windows-hip 95.77) | unchanged — accepted `95.99` not imported | deferred (needs GPU) |
| 4 | HunyuanOCR evidence quality | `92.09` (no committed artifacts) + `93.64` both valid | unchanged — multi-backend w/ one primary is allowed | deferred (evidence gap) |

## Data migrations (Commit ②)

- **Re-file** (ADR-0017): `hub/imports/mineru2.5/mineru2-5__{linux-rocm,windows-hip}__pipeline__*` → `hub/imports/mineru-pipeline/mineru-pipeline__…`; `model_id`+`result_id` prefix changed, `primary=true`, `license_category=restricted`. `run_spec` (the producer run record) left unchanged; only the zone classification moved. `registry.yaml` `mineru-pipeline` overalls `null`→`86.48`/`86.59`.
- **Invalidate**: `hub/imports/unlimited-ocr/…__vllm__…__6bf73567be17` `status` `valid`→`invalid` (150-page canary, `full_set=false`, own note "FAILING").
- **License unify**: `license_category` set on 7 imports (logics/ovis/paddle→`open-source-ai`; mineru2.5 VLM×2 + the 2 moved pipeline→`restricted`), each with a `license_category_note`/`classification_note`/`lifecycle_note` audit trail.

Each edited `imported-result.json` carries a `Phase-0 Commit 2 …` note. `source.json` / `source_sha256` untouched (evidence pointers preserved; only re-validated at import time, not on direct edit).

## New detectors (Commit ①)

`check_drift` rules (report-only, no auto-fix): `pipeline-and-vlm-same-model-id`,
`canary-track-result-valid`, `license-category-drift` (last gated on optional
`registry_rows`, mirroring `registry_scores`). Wired into the `check-drift` CLI +
`QUALITY_STATUS.md` renderer. Plus a NOT_RUN anti-rewrite guard and
`tests/test_canonical_no_defects.py` (real-data regression; future regressions fail CI).

## Verification (commands + results)

```
python -m omnidocbench_rocm.cli check-drift --hub-dir hub --registry hub/registry.yaml --canonical hub/canonical_results.json
  → {"findings": [], "count": 0}   (was 6 after Commit ①; 0 after Commit ②)
make ci
  → ci: all gates green ✓   (321 passed; validate_registry / registry generate --check /
     comparison-table --check / check_brand / check_license_class / check_result_ids /
     build / pytest / quality-status freshness all green)
```

canonical: 22 rows / **10 valid** (was 11; unlimited 22.3 → invalid).

## Deferred (need GPU + GA-7.14/torch-2.11 env)

- HunyuanOCR README headline `llama.cpp 92.09` has no committed artifacts (model_card admits "machine-local"); the evidenced `93.64` vLLM / `94.05` transformers sit valid/superseded — inverted evidence quality.
- Unlimited-OCR `92.451` is self-reported (no hash manifest, no official scorer JSON, README `result_id` ≠ actual manifests).
- PaddleOCR-VL accepted `95.99` (Linux/ROCm) not imported to central; Paddle revision `not_recorded`; Logics model weights float on `master`.
