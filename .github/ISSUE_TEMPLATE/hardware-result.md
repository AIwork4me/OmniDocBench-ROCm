---
name: Hardware run report
about: Submit a real run report on an AMD GPU / ROCm version (raises cross_hardware_reproduction over time)
title: "[Hardware] <model> on <GPU> / ROCm <version>"
labels: hardware-run
---

## Which contribution path?
- [x] Share a hardware run (ROCmDoc Standard §8 cross_hardware_reproduction)

## Model + result identity
- Model repo:
- `result_id` (if reproducing an existing one) or new run:
- Comparison track (`omnidocbench-v1-6-full-default-…`):

## Hardware / software
- GPU (e.g. gfx1100 / MI300 / Strix Halo):
- ROCm version:
- Backend + precision (e.g. vLLM bf16, llama.cpp q8_0):

## Evidence attached (immutable)
- Run stats `_run_stats.json`:
- Prediction manifest (files + count + sha256):
- Page-set coverage (full 1651? subset?):
- Metric result + provenance:

## Reproduction command
```
<exact adapter command + env>
```

## Honesty checklist
- [ ] Single-page failures entered the denominator (not silently excluded).
- [ ] No smoke/placeholder output passed off as real OCR.
- [ ] `resolved_platform` / `actual_backend` are the real values (not the request).
