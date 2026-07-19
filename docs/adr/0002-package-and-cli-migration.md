# ADR-0002: Package and CLI migration; legacy surface dropped

- **Status:** Accepted
- **Date:** 2026-07-19

## Context

In 0.1.0 the product was `OmniDocBench-AMD`, the (unpublished) PyPI
distribution was `omnidocbench-amd`, the Python package was
`omnidocbench_amd`, and the CLI was `omnidocbench-amd`. ADR-0001 reframes the
project around the ROCm software stack, which requires a matching public
identity. The open question was whether to ship a backward-compatible
"legacy alias" surface (`import omnidocbench_amd`, `omnidocbench-amd --help`)
during a deprecation window, as a literal reading of the migration brief
initially suggested.

## Decision

Rename, and **drop the legacy compatibility surface entirely** in 0.2.0:

| Dimension | 0.1.0 | 0.2.0 |
|---|---|---|
| Product / GitHub repo | OmniDocBench-AMD | **OmniDocBench-ROCm** |
| PyPI distribution | omnidocbench-amd (never published) | **omnidocbench-rocm** |
| Python package | omnidocbench_amd | **omnidocbench_rocm** |
| CLI | omnidocbench-amd | **omnidocbench-rocm** |
| Template default repo | Model-AMD | **Model-ROCm** |
| Version | 0.1.0 | **0.2.0** |

There is **no** `omnidocbench_amd` shim module, **no** `omnidocbench-amd`
console-script alias, and **no** second PyPI distribution. Only
`omnidocbench-rocm` / `omnidocbench_rocm` exists as the public surface.

## Justification (evidence)

Per the migration audit (`docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`):

- `omnidocbench-amd` was **never published** to PyPI (HTTP 404).
- `omnidocbench-rocm` is **available** (HTTP 404 today).
- The three model repos (`HunyuanOCR-ROCm`, `MinerU-ROCm`, `Unlimited-OCR-ROCm`)
  do **not** pip-depend on this package; the old name appears only in
  narrative docs. **No real downstream consumers exist.**

Because the brief's compatibility-window clause was explicitly
evidence-gated ("if confirmed never published and no downstream, the
compatibility package may be simplified"), and the evidence confirms both
conditions, the cleanest, least-confusing choice is to drop the legacy
surface entirely. This removes dual-maintenance, the 0.3.0 removal cliff,
and user-facing confusion ("do I install `-amd` or `-rocm`?").

## Consequences

- Users install `omnidocbench-rocm` and run `omnidocbench-rocm`. There is no
  old name to keep working or to later remove.
- The conformance checker requires `omnidocbench-rocm` as a model-repo
  dependency; a repo depending on the old name fails conformance with a clear
  message.
- CI has a brand-residue gate (`scripts/check_brand.py`) that forbids the old
  brand everywhere except internal-record paths
  (`docs/superpowers/**`, `docs/audits/**`, `docs/adr/**`, `CHANGELOG.md`).
- The CHANGELOG entry records the rename; that is the only forward pointer
  (no separate migration guide is needed for a name that was never
  distributed).

## Reversibility

Low cost. If a real downstream consumer of `omnidocbench-amd` ever appears, a
thin shim distribution can be published later without touching the ROCm
package.
