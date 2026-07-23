# ROCm Document Parsing Zone — Design Spec

- **Date:** 2026-07-23
- **Status:** Draft (for review)
- **Origin:** `/grill-with-docs` session 2026-07-23; consolidates the grilled
  consensus into a design for the `writing-plans` handoff.
- **Glossary:** [`CONTEXT.md`](../../../CONTEXT.md). **Decisions of record:**
  [ADR-0003](../adr/0003-trust-bar-and-reproduction-depth.md),
  [ADR-0004](../adr/0004-catalog-scope-and-curation-policy.md),
  [ADR-0005](../adr/0005-entry-points-no-production-runtime-cli.md),
  [ADR-0006](../adr/0006-licensing-posture.md)
  (0001/0002 predate this session).

---

## 1. Vision

An open-source **Zone** where developers can find, compare, and trust
document-parsing models that run on **AMD Radeon GPUs** (RDNA3 / gfx1100 /
Strix Halo). Trust is the product: every entry earns its place through
**rigorous, complete, reproducible evaluation** on OmniDocBench v1.6 — not "it
ran a demo." The Zone is positioned for the Radeon developer ecosystem and
aligns with the **AMD Radeon Developer Cloud (China)** at
`radeon.anruicloud.com`, the canonical place developers obtain Radeon 7900 XTX
hardware.

## 2. Starting point (what already exists)

- **5 repos** under `AIwork4me`: the hub/engine `OmniDocBench-ROCm`, plus
  `HunyuanOCR-ROCm`, `MinerU-ROCm`, `PaddleOCR-VL-ROCm`, `Unlimited-OCR-ROCm`.
- **Topology A**: one platform repo (contracts, engine, template, registry,
  docs) + per-model repos; the engine never imports an adapter — it consumes
  filesystem output — so scores are comparable across stacks.
- **Trust machinery already built**: 3-tier badges
  (`community-wanted` → `community` → `verified`), honest "no AMD GPU CI"
  posture, 9-step `contribute-a-model` flow, cookiecutter template, provenance
  artifacts, CDM scoring, `Dockerfile.repro` scoring-repro.
- **Realization gap today**: 2 of 4 models unscored (`unlimited-ocr`,
  `hunyuan-ocr` are `community-wanted`); **0 models `verified`**; no hosted
  site (registry renders to Markdown only).

## 3. The locked design

| Area | Decision | ADR |
|---|---|---|
| Spine | `OmniDocBench-ROCm` is the hub / eval-trust engine | — |
| Trust bar | Floor `community` (unscored → incoming lane); apex `verified` = scoring-repro in pinned Docker (±0.5) **+ a committed anyone-can-run reproduction recipe**; **not** maintainer inference-repro, **not** a self-hosted runner. Completeness = full-set + mandatory CDM + per-category breakdown + efficiency metrics | 0003 |
| Catalog | **Hybrid**: `verified` flagship comparison (homepage headline) + open `community` tail (secondary) + external-reference link-out. Hard tier separation. Open-source only. Reference set = the 4 current models, with a published selection policy + graduation rule | 0004 |
| Topology | Single hub repo; MkDocs site in `docs/`; no separate portal repo | — |
| Entry points | `omnidocbench-rocm` is the unified entry for eval (`run`) and single-doc parse (`infer`); production parsing uses per-model CLIs; **no** unified runtime CLI; add cheap `list`/`doctor` discovery | 0005 |
| Naming | Keep `OmniDocBench-ROCm` + "ROCm Document Parsing Zone" tagline | — |
| Licensing | Hub stays Apache-2.0 (clean: no code import, no weight redistribution). Accept restrictive-open (MinerU OSL, Tencent Hunyuan) **with prominent license + commercial-use disclosure**. No-license weights = hard gate (PDF-Extract-Kit-1.0 must resolve or be excluded) | 0006 |
| Hardware | **Radeon RDNA3 (gfx1100 / RX 7900 XTX / W7900) + Strix Halo** = verified reference. Other ROCm archs (incl. Instinct/MI300 CDNA) = community-only. `radeon.anruicloud.com` Radeon Cloud = reproduction hardware + audience channel | — |

## 4. Target state (the Zone when "done")

- **Flagship comparison** (homepage, `verified`-only): the 4 reference models,
  `verified` on `linux-rocm`, each showing **full-set** results with **CDM**,
  a **per-category breakdown**, **efficiency** (s/page, peak VRAM, GPU), and a
  **license / commercial-use** column.
- **Community tail**: open-source contributions, `community`-badged, in a
  secondary "also evaluated" section.
- **External reference**: a clearly-labelled link-out to the OmniDocBench paper
  for closed-SOTA calibration — never inlined, never badged.
- **Hosted MkDocs site** rendered from `hub/registry.yaml`, deployed from the
  hub repo's `docs/`.
- Each model repo carries: a `NOTICE`, `license` + `commercial_use` in
  `model_card.json`, and (for `verified`) a committed **reproduction recipe**.
- A `docs/selection-policy.md` (reference-set criteria + graduation rule).
- `omnidocbench-rocm list` / `doctor` discovery subcommands.

## 5. Realization scope (workstreams for `writing-plans`)

Not sequenced here — `writing-plans` orders these into an incremental plan. Each
maps to a decision above.

1. **Onboard the 2 pending models to `community` on `linux-rocm`.** For
   `unlimited-ocr`: run via its working backend (PyTorch path is known-good;
   vLLM is numerics-blocked). For `hunyuan-ocr`: stand up the verified
   `/opt/venv` vLLM 0.16.1 path. Produce full-set + CDM bundles. *(ADR-0004)*
2. **Efficiency metrics.** Extend the artifact schema + `run_summary.json` with
   an efficiency section; the adapter reports s/page, peak VRAM, GPU via
   `_run_stats.json`; surface in the comparison table. *(ADR-0003)*
3. **Renderer 3-tier split.** `scripts/generate_registry.py` + the MkDocs site
   split flagship (`verified`) / community (`community`) / external-reference
   (link-out), with the incoming lane for `community-wanted`. *(ADR-0003/0004)*
4. **Reproduction recipe.** Define the recipe artifact (distinct from the audit
   `provenance.adapter_command`); add it to `contracts/conformance.md` as a
   `verified` prerequisite. *(ADR-0003)*
5. **Push the 4 reference models to `verified`.** The `verified` gate is
   **CPU-only scoring-repro** in `Dockerfile.repro` (re-scores committed
   predictions, ±0.5, recorded in `VERIFIED.yaml`) — **no GPU required for the
   gate itself**. Radeon hardware (local gfx1100 or anruicloud 7900 XTX) is
   needed only for the *inference* steps: onboarding (workstream 1) and
   demonstrating the reproduction recipe (workstream 4). *(ADR-0003)*
6. **MkDocs site.** Stand up the hosted site from `docs/`, rendering the
   registry; stable/citable URLs. *(roadmap)*
7. **Licensing surfaces.** Standardize the per-repo `NOTICE` (MinerU template);
   add `license` + `commercial_use` to `model_card.json` and the registry
   renderer; resolve or exclude PDF-Extract-Kit-1.0 (restrict MinerU's verified
   path to its Apache-2.0 MinerU2.5-Pro VLM weights until clarified).
   *(ADR-0006)*
8. **Selection policy doc.** Publish reference-set criteria + graduation rule
   (extends `governance.md` or new `docs/selection-policy.md`). *(ADR-0004)*
9. **Discovery subcommands.** `omnidocbench-rocm list` (models + badges) and
   `doctor` (is a model provisioned: venv/weights/backend). *(ADR-0005)*
10. **Radeon Cloud alignment.** A "document parsing on Radeon" workshop/notebook
    for the anruicloud ecosystem + cross-link; document anruicloud as the
    reproduction-hardware option. *(hardware decision)*

## 6. Explicit non-goals / deferred

- **Self-hosted GPU runner** (ADR-0003) — deferred; revisit when catalog/bandwidth
  justify. anruicloud Radeon hardware substitutes for manual reproductions meanwhile.
- **Unified production runtime CLI** (ADR-0005) — out of scope; the Zone does not
  own a runtime.
- **Datacenter Instinct/MI300 as a first-class target** — Radeon focus.
- **Inlining closed-model numbers** (ADR-0004) — link-out only.
- **Auto-promoting `community` → `verified`** — never; `verified` is
  maintainer-assigned.

## 7. Open questions for review

- **MinerU + PDF-Extract-Kit**: confirm the interim stance — MinerU `verified`
  via its Apache-2.0 MinerU2.5-Pro VLM weights only, until PDF-Extract-Kit-1.0's
  license is clarified upstream. (ADR-0006)
- **`unlimited-ocr` backend**: confirm scoring via the PyTorch path (vLLM
  numerics-blocked) is acceptable for its `community`/`verified` path. (realization)
- **Site hosting**: GitHub Pages from the hub repo, or elsewhere?
- **anruicloud depth**: just cross-link/workshop, or also a documented
  reproduction-hardware procedure?
- **Efficiency metrics feasibility**: peak VRAM is straightforward for
  vLLM/transformers backends but harder for ONNX pipelines — confirm whether
  efficiency is mandatory-or-best-effort per backend. *(ADR-0003)*
- **Tagline wording**: "ROCm Document Parsing Zone" vs "Radeon Document Parsing
  Zone" — the hardware focus is Radeon; lean the tagline toward Radeon?
  *(naming)*
- **windows-hip `verified`**: blocked until the windows-hip backend lands
  (roadmap, medium-term); linux-rocm `verified` is the first target. *(ADR-0003)*
