# ADR-0020: Central lightweight-contracts package boundaries

- **Status:** Accepted (Round-2 dependency hygiene; internal boundaries first)
- **Date:** 2026-07-28

## Context

A model repo that only wants the CLI/identity/contract surface should not have
to install the full OmniDocBench engine (scorer, dataset download, heavy deps).
Conversely, conformance logic and the benchmark engine should be separable so
their release cadences can differ.

## Decision

Establish three logical layers with a **correct dependency direction**, as
internal module boundaries first (no risky one-shot repo split):

```
rocmdoc-contracts      schemas, enums, result identity, comparison tracks,
                       exit codes, lightweight models, validators
        ^
rocmdoc-conformance    behavioral tests, fake-runtime harness, CLI runner,
                       evidence-integrity, score reproduction
        ^
omnidocbench-rocm      benchmark engine, scorer, central import, reviews,
                       Hub generation
```

In the current single wheel these map to cohesive module groups:

- **contracts**: `schema`, `run_spec`, `tracks`, `primary`, `cli_contract`,
  `license_class`, `assurance` (the producer/platform enums), `types`.
- **conformance**: `conformance`, `conformance_profiles`, `bundle_validator`.
- **engine/hub**: `cli`, `source_import`, `hub`, `registry`, `stages`,
  `backends`, `migrate`, `model_card_v2`, `artifact_utils`, `download_*`.

Rules (enforced going forward):

1. A sub-repo's **runtime** dependency is the lightweight contracts only
   (`omnidocbench-rocm` core already pulls just `huggingface_hub`/`jsonschema`/
   `pyyaml`/`rfc3339-validator` — no torch/vllm/paddle).
2. Conformance is a **dev/test** dependency; the benchmark engine is an **eval**
   dependency (optional extras).
3. The dependency direction is contracts ← conformance ← engine; never reversed.
4. `spec-lock.json` records a **cohort**
   (`contract_release` / `conformance_release` / `central_commit`) — pinning one
   SHA alone does not express cross-repo compatibility.
5. A future split into three independently-versioned packages is enabled by these
   boundaries but **not** performed now (avoids a high-risk one-shot split).

## Consequences

- `version`/`capabilities`/`doctor` run without torch; sub-repos install light.
- A clean seam exists for a later multi-package release.

## Reversibility

- Internal boundaries only; no published package split yet. Reverting is a
  re-merge of module groups (they already coexist in one wheel).
