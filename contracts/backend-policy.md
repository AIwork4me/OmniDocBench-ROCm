# Backend Policy

This contract defines which inference backends OmniDocBench-ROCm supports,
and the conditions under which a non-ROCm backend may appear. It is the
normative reference for badge eligibility and for honest provenance. See
ADR-0001 for the project-boundary decision this policy enforces.

The platform keys are `linux-rocm` and `windows-hip` (retained; Windows is
not renamed because its technical entry point remains the HIP SDK, and HIP
is part of ROCm).

## 1. First-class ROCm backends

These are the project's long-term support targets. A result produced with one
of these backends is eligible for the normal badge tiers
(`contracts/badge-policy.md`):

- **HIP Runtime / HIP SDK**
- **MIGraphX**
- **ONNX Runtime MIGraphX Execution Provider**
- **PyTorch-ROCm**
- **vLLM-ROCm**
- **llama.cpp-HIP**
- other open-source inference paths explicitly built on ROCm/HIP.

## 2. Transitional backend — DirectML

**DirectML** is permitted *only* on Windows, and only where an equivalent
ROCm/MIGraphX capability is not yet available. It is a **temporary
compatibility fallback**, not a first-class backend and not a peer of the
ROCm paths above.

A model that uses DirectML must satisfy **all** of the following:

1. Its documentation labels the path `compatibility fallback`.
2. It does **not** receive any badge whose meaning implies "ROCm-native".
3. Its provenance records the real execution provider
   (`DmlExecutionProvider`) in the artifact's `execution_provider` field.
4. Its results are **never** described as MIGraphX or ROCm-EP results.
5. Its `model_card.json` records the future target backend as MIGraphX (in
   `target_backend`) — the intended ROCm path.
6. When a production-ready Windows ROCm/MIGraphX path exists, the DirectML
   path enters a `deprecated` → `removed` flow.

We state plainly: **Windows MIGraphX is not currently production-ready.** We
quote no AMD/ROCm/ONNX Runtime roadmap or release date.

## 3. Out of scope

- **Vulkan**
- **OpenVINO**
- general non-ROCm GPU backends.

These are not project backends. They may be mentioned only to state that they
are out of scope; they are not recommended in templates or docs.

## 4. Dimension separation

A single `platform` string must not carry platform + OS + runtime +
execution-provider + compatibility-status at once. The artifact schema
(`contracts/artifact-schema.json`, schema v1) keeps `platform`
(`linux-rocm` | `windows-hip`) and adds **optional** fields so each dimension
is recorded independently:

| Field | Meaning | Example |
|---|---|---|
| `backend` | runtime / serving stack | `vllm-rocm`, `migraphx`, `onnxrt-migraphx`, `llama-cpp-hip`, `smoke` |
| `execution_provider` | ONNX EP (when applicable) | `ROCMExecutionProvider`, `DmlExecutionProvider` |
| `backend_family` | kin group | `rocm`, `directml-fallback` |
| `compatibility_status` | standing | `first-class`, `transitional-fallback` |
| `target_backend` | future intended backend (for fallback rows) | `migraphx` |

`schema_version` stays `1`; these additions are backward-compatible and do
not invalidate any existing v1 artifact.
