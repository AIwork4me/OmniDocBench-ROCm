# ADR-0005: Entry points — eval harness is the unified entry; no production runtime CLI

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The Zone exposes inference two ways: the platform CLI (`omnidocbench-rocm`, the
eval harness) and each model repo's own CLI (`hunyuan-ocr`, `mineru-rocm`,
`paddleocr-vl-rocm`, `unlimited-ocr`). Whether to add a third, unified
"production parsing" runtime CLI (an ollama-style `ocr-rocm run --model X`
that manages backends) was an open question.

## Decision

The eval harness `omnidocbench-rocm` is the Zone's **unified entry**. It
already dispatches to any model for both evaluation (`run`) and
single-document parsing (`infer --adapter <model>/adapter/run_adapter.py`)
over the filesystem-decoupled adapter contract — the same path that makes
scores comparable. **Production parsing uses each model's own CLI.**

The Zone deliberately does **not** ship a unified production *runtime* CLI
that manages inference backends (vLLM / llama.cpp / ONNX). That is out of
scope: the Zone does not own a runtime.

A thin discovery / readiness layer (`list` models + badges; `doctor` to check
a model is provisioned) is added under the existing CLI as a low-cost
convenience; it does not manage backends.

## Consequences

- Two surfaces remain: `omnidocbench-rocm` (eval + single-doc `infer` +
  `list`/`doctor`) and per-model CLIs (production). No third runtime CLI.
- The adapter contract is the single integration seam — both eval and
  production parse flow through it, so there is no parallel interface to drift.
- `omnidocbench-rocm infer` is the documented way to parse a single document
  with any model uniformly.

## Reversibility

Low cost. If production-parsing demand later justifies a dedicated thin
`parse` gateway, it can layer over the same adapter contract without changing
the per-model CLIs. A full runtime CLI stays out of scope unless the Zone
takes ownership of a runtime.
