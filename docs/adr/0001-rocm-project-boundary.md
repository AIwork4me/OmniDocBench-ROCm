# ADR-0001: ROCm project boundary

- **Status:** Accepted
- **Date:** 2026-07-19
- **Supersedes:** the implicit "AMD Doc Parsing zone" scope in the deleted
  `2026-07-12-amd-doc-parsing-platform-foundation-design.md`

## Context

The project adapts open-source document-parsing models to AMD hardware and
evaluates them on OmniDocBench v1.6. Until 0.1.0 it was branded
"OmniDocBench-AMD" / "AMD Doc Parsing zone", which conflates the vendor with
the software stack and blurs the line between ROCm-native paths and
non-ROCm backends (DirectML, Vulkan, OpenVINO). Contributors and readers
need an explicit, durable definition of what this project does and does not
support.

## Decision

The long-term scope of **OmniDocBench-ROCm** is the AMD ROCm open-source
compute software stack.

**First-class ROCm backends** (the project's long-term support targets):

- HIP Runtime / HIP SDK
- MIGraphX
- ONNX Runtime MIGraphX Execution Provider
- PyTorch-ROCm
- vLLM-ROCm
- llama.cpp-HIP
- other open-source inference paths explicitly built on ROCm/HIP

**Transitional backend:**

- **DirectML** — permitted *only* on Windows where an equivalent
  ROCm/MIGraphX capability is not yet available. It is a *temporary
  compatibility fallback*, not a peer of the ROCm backends.

**Out of scope:**

- Vulkan
- OpenVINO
- general non-ROCm GPU backends

The platform keys `linux-rocm` and `windows-hip` are retained: `windows-hip`
is not renamed to `windows-rocm`, because the Windows technical entry point
remains the HIP SDK and HIP is part of ROCm.

## Consequences

- DirectML results must be labelled `compatibility fallback` in model
  documentation; they cannot earn a "ROCm-native" meaning badge.
- Provenance must record the real execution provider; a DirectML result must
  never be described as a MIGraphX or ROCm-EP result.
- A model using DirectML must record its target backend as MIGraphX (the
  intended ROCm path) and enter a deprecated→removed flow once a real
  Windows ROCm/MIGraphX path is available.
- The artifact schema carries optional fields (`backend`,
  `execution_provider`, `backend_family`, `compatibility_status`,
  `target_backend`) so that platform, operating system, runtime/backend,
  execution provider, and compatibility status are separate dimensions
  rather than overloaded onto a single `platform` string.
- We state plainly that Windows MIGraphX is **not** currently
  production-ready, and we quote no AMD/ROCm/ONNX Runtime roadmap or release
  date.
