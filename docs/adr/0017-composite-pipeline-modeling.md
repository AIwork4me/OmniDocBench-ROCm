# ADR-0017: Composite pipeline modeling (components)

- **Status:** Accepted (Round-2 correctness for mixed pipelines)
- **Date:** 2026-07-28

## Context

Several models (PaddleOCR-VL, MinerU) are **composite pipelines**: a layout
engine (e.g. PP-DocLayoutV3 on ONNX Runtime / DirectML) feeding a VLM (llama.cpp
/ vLLM on HIP) with CPU preprocessing and a rendering/postprocessing stage. v2's
single `implementation.backend` could not express this: a Windows pipeline using
a DirectML layout stage was labeled `backend=rocm`, which is false.

## Decision

Model an implementation as **components** (schema `$def component_record`;
`result_record.components` / `topology` / `accelerator_family`):

```
topology: embedded-python | managed-local-server | external-server | native-binary
components:
  layout:    {engine, runtime, execution_provider, requested_provider, actual_provider, ...}
  vlm:       {model, runtime, acceleration, topology, ...}
  ocr:       {engine, runtime, ...}
  rendering: {engine, dpi, ...}
  postprocessing: {engine, revision, ...}
accelerator_family: rocm | hip | directml | cpu | mixed
```

Rules (enforced):

1. `requested_provider` and `actual_provider` are recorded **separately** per
   component.
2. A pipeline with any non-ROCm stage is `accelerator_family=mixed`, **never**
   `rocm`. A DirectML layout stage must not be labeled ROCm.
3. CPU preprocessing is expressible (and allowed) as a component.
4. A component change feeds into `run_spec_hash` (ADR-0015) → a new identity.
5. `doctor` checks per component; `capabilities` reports per component; the Hub
   can show "which stages use AMD acceleration".

## Consequences

- PaddleOCR-VL / MinerU are honestly classified as `mixed`, not `rocm`.
- Per-stage provider drift (requested vs actual) is visible.

## Reversibility

- Additive `$defs` + optional fields. A single-backend repo simply omits
  `components` and sets `accelerator_family` to its one family.
