# OmniDocBench-ROCm zone — ubiquitous language

The shared vocabulary of the AMD ROCm open-source document-parsing **zone**:
one platform repo (`OmniDocBench-ROCm`) holding the eval engine, contracts,
and hub registry, plus per-model repos generated from its template. **Trust
is the product** — every entry earns its place through rigorous, complete,
reproducible evaluation. (中文「专区」= **zone**.)

## The zone and its surface

**Zone**:
The whole ecosystem — the platform repo plus all per-model repos.
_Avoid_: platform, project, hub (those name specific things below).

**Hub**:
The public comparison surface rendered from `registry.yaml` (Markdown today; a
hosted MkDocs site is planned). The front door of the zone.
_Avoid_: site, portal, registry (the registry is the data source, not the surface).

**Comparison table**:
The ranked, trustworthy table. Only models at `community` or above appear;
unscored models never appear here.

**Incoming lane**:
The separate listing for models with no committed result on a platform
(`community-wanted`). Signals "wanted here, not yet measured"; never mixed
into the comparison table.

## Catalog & curation

**Reference set**:
The curated flagship models the Zone commits to keeping evaluated and
reproducible — the trust anchor. Membership follows a published selection
policy (coverage of the major open doc-parsing architectural families; one
representative per family; runnable on consumer AMD cards), not personal
preference.

**Flagship comparison**:
The headline, `verified`-only ranking on the hub homepage. Only `verified`
reference-set models appear here; it is the table developers trust for
cross-model comparison.

**Community tail**:
Open-source models contributed via the template, `community`-badged and
self-attested. Shown in a secondary "also evaluated" section, never mixed into
the flagship comparison.

**Graduation rule**:
The published conditions under which a community model is promoted into the
reference set (`community` status + sustained demand + maintainer bandwidth to
verify it each release).

**External reference**:
Closed-SOTA numbers from the OmniDocBench paper, shown only as a clearly-labelled
link — never inlined into any Zone table, never badged. The Zone shows only
numbers it produced under its pinned contract.

_Avoid_: inlining closed-model numbers; mixing community and verified rows.

## Licensing

**Open-source (catalog line)**:
Open weights + open code — and this *includes restrictive-open* licenses, not
only permissive/OSI-compatible ones.
_Avoid_: reading "open-source only" as "permissive only."

**Restrictive-open**:
An open license that adds commercial-use conditions (e.g. MinerU Open Source
License, Tencent Hunyuan Community License). Accepted in the catalog, but the
model must disclose its license and commercial limits prominently.

**No-license weights**:
Weights with no declared, resolvable license (e.g. PDF-Extract-Kit-1.0). A hard
block on listing or verification until the license is clarified or the weights
path is excluded.

## Badges (trust tiers)

**community-wanted**:
No committed result on this platform yet. Backs nothing; the default for an
absent platform.

**community**:
Provenance-complete and conformant; self-attested, CI-verified for structure.
Real if you trust the contributor; not independently reproduced.

**verified**:
A maintainer reproduced the committed `overall` in pinned Docker within
tolerance. The only independently-reproduced tier — the one to trust for
cross-model comparison.

_Avoid_: calling any CI-green check "verified." CI has no AMD GPU runner;
trust comes from the badge, not the CI status.

## Reproduction

**Scoring-repro**:
Re-running the *scoring* (Edit_dist + TEDS + CDM) from the committed
predictions in a pinned toolchain. Deterministic given the predictions. The
`verified` gate.

**Inference-repro**:
Re-running the model's *inference* to regenerate predictions on AMD hardware.
Noisy across ROCm/driver/hardware; deliberately **not** a gate (ADR-0003).

**Reproduction recipe**:
A committed, environment-portable, pasteable record of how to regenerate a
model's inference — exact command, pinned weights revision, backend,
venv/Docker. Makes inference *verifiable by anyone*.

_Avoid_: confusing the recipe (how to reproduce) with the audit-only
`provenance.adapter_command` (what ran once). They are different artifacts.

## Evaluation

**Complete (全亮)**:
The disclosure standard for a trustworthy entry — full dataset, mandatory
CDM, per-category breakdown, and efficiency metrics, all committed and
rendered.

**CDM**:
Consistent Distance Metric — formula-recognition quality via
LaTeX→PDF→PNG color matching. The hardest, highest-value metric.

**Provenance-complete**:
A result bundle committed with schema-valid `run_summary.json` +
`provenance.json`, recording exactly what ran (real prediction dir,
adapter-reported backend, audit command) and the pinned inputs (dataset
revision, engine version, git commit).

## Dimensions (do not overload)

**Platform**:
The OS+stack category — `linux-rocm` or `windows-hip`. Badges are
per-platform and independent.

**Backend**:
The inference path a model uses — `vllm`, `llama-cpp-server`, `onnx-rocm`,
`onnx-directml`, etc.

**Execution provider**:
The ONNX Runtime EP actually used — ROCm-EP vs DirectML. A DirectML result is
a *compatibility fallback*, never ROCm-native (ADR-0001).

_Avoid_: cramming platform, backend, and execution provider into one string;
they are separate dimensions.

## Hardware focus

**Radeon (reference hardware)**:
AMD consumer/workstation GPUs — gfx1100 / RDNA3 (Radeon RX 7900 XTX, Radeon PRO
W7900) and Strix Halo. The verified-reference family; `verified` results are
reproduced here.
_Avoid_: "ROCm GPUs" as if all archs are equal — Radeon is the reference, other
archs are community.

**Instinct / MI300 (CDNA)**:
AMD datacenter GPUs. Out of first-class scope; reachable only via the community
tail if a contributor with that hardware evaluates a model there.

**Radeon Cloud (anruicloud)**:
`radeon.anruicloud.com` — the AMD Radeon Developer Cloud (China region),
providing cloud Radeon 7900 XTX access. The canonical place developers obtain
the reference hardware; usable for maintainer reproductions and as an audience
channel (not a CI runner).

## v2 vocabulary (ADR-0007 → 0012)

**Result record**:
The atomic unit of evidence — ONE combination of platform + backend + precision +
benchmark, with its own `status`, `assurance`, `metrics`, `provenance`. A Model
Card v2 holds a `results[]` array of these. result_id is unique + reproducibly
generated from the tuple.
_Avoid_: putting two combinations' scores in one record.

**result_id**:
A deterministic id for a result record: `<model>__<platform>__<backend>__<precision>__<benchmark>__<sha12>`.
Same tuple → same id; the join key between cards, the manifest, and canonical_results.

**Assurance**:
The specific reproduction depth of a result — `submitted` | `evidence-complete` |
`score-reproduced` | `inference-reproduced` | `cross-hardware-reproduced`. Per
result; never propagates across results. The precise replacement for the single
`verified` badge (ADR-0008).
_Avoid_: a model-wide "verified"/"assurance" field; collapsing assurance to one word.

**Manifest (rocmdoc.yaml)**:
A capability declaration (platforms/backends/licenses/interfaces) — NOT a result.
Result alignment forbids a result from claiming a platform the manifest does not
declare (no faking support, ADR-0009).
_Avoid_: putting a score in the manifest; conflating "declared" with "measured".

**Canonical results (single source of truth)**:
`hub/canonical_results.json` — the ONLY place scores live. The README results
section + hub table are derived from it; `generate --check` catches drift
(ADR-0012). No auto-pick-highest-as-primary.
_Avoid_: hand-writing a score in the README or registry.

**License category**:
Normalized classification — `open-source-ai` | `open-weights` | `source-available`
| `restricted` | `closed` | `unknown`. Default for any unclear license is
`unknown`, NEVER `open-source-ai` (ADR-0010).

**Standard CLI**:
The v2 adapter surface — `version`/`capabilities`/`doctor`/`parse --json` with a
fixed exit-code scheme. The central repo validates it; never imports a runtime
(ADR-0011).

