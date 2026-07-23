# ADR-0006: Licensing posture

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The Zone links to per-model repos whose licenses are heterogeneous and include
*restrictive-open* terms: the MinerU pipeline (MinerU Open Source License —
Apache-2.0 plus a commercial threshold at MAU >100M or revenue >$20M),
HunyuanOCR (Tencent Hunyuan Community License, commercial-use conditions),
alongside permissive MIT/Apache (PaddleOCR-VL, Unlimited-OCR). One weights set
(PDF-Extract-Kit-1.0) has no declared license at all. Three questions: how do
these coexist with the Apache-2.0 hub; what does the ADR-0004 "open-source
only" catalog line actually permit; and how is the no-license weights case
handled?

## Decision

**Coexistence (clean by architecture).** The hub stays Apache-2.0 and is never
contaminated: Topology A means it imports no model code and redistributes no
weights — each repo keeps its own license, weights are downloaded per-repo, and
the registry only links. No derived-work mixing occurs. Each model repo must
ship a `NOTICE` (LICENSE OVERVIEW + COMPONENT LICENSES + a "not affiliated or
endorsed" disclaimer + an explicit copyleft/AGPL status), modelled on
`MinerU-ROCm/NOTICE`; the SPDX `LICENSES/` + `REUSE.toml` variant (as in
HunyuanOCR-ROCm) is accepted. This is a conformance requirement.

**The "open" line (accept restrictive-open, with disclosure).** "Open-source
only" (ADR-0004) means open weights + open code, and this **includes
restrictive-open licenses** (MinerU Open Source License, Tencent Hunyuan
Community License). Tightening to OSI/permissive-only is rejected because it
would exclude HunyuanOCR and MinerU — half the reference set. In exchange, each
model must disclose its license and any commercial-use restrictions prominently:
`model_card.json` carries `license` and `commercial_use` fields, surfaced as a
hub column, so a commercial user is never misled. (Same posture as HuggingFace
labelling non-commercial/restrictive licenses.)

**No-license weights = hard gate.** A declared, resolvable license is required
for both code and weights. The PDF-Extract-Kit-1.0 case (no declared license)
must be resolved upstream or the affected weights path excluded before it can
be listed or verified. For MinerU this means scoring only via the
Apache-2.0-weights path (MinerU2.5-Pro VLM) until PDF-Extract-Kit is clarified.

## Consequences

- Conformance gains: a per-repo `NOTICE` requirement, and `license` +
  `commercial_use` fields in `model_card.json` (rendered on the hub).
- Restrictive-open models are listed, but their commercial limits are visible;
  the Zone never asserts they are "free for all commercial use."
- The PDF-Extract-Kit ambiguity blocks the MinerU pipeline path until resolved;
  MinerU is evaluated via its licensed VLM path in the meantime.
- The hub repo itself stays a single-license (Apache-2.0) project; no LICENSES
  aggregation of model licenses is needed because nothing is combined.

## Reversibility

- The NOTICE / disclosure requirements are easily tightened or loosened.
- The "accept restrictive-open" line is the load-bearing choice: reversing it
  (to OSI-only) would remove HunyuanOCR and MinerU from the catalog. Recorded
  so that choice is deliberate, not accidental drift.
