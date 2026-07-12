# OmniDocBench-AMD

The shared platform for the **AMD Doc Parsing** zone: run OmniDocBench v1.6
open-source document-parsing models on AMD hardware (Radeon + Linux/ROCm, and
Ryzen AI MAX+ 395 + Windows/HIP), with real eval data, out-of-the-box demos,
and bilingual docs.

- `contracts/` — the adapter interface, artifact schema, conformance checklist, badge policy.
- `engine/` — the dual-platform eval engine (pip package).
- `template/` — cookiecutter for a per-model repo.
- `hub/` — model registry + site.

See `docs/contribute-a-model.md` to add a model. Spec: `docs/superpowers/specs/`.
