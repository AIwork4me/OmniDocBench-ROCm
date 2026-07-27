# ADR-0009: rocmdoc.yaml — capability declaration vs. result

- **Status:** Accepted (additive; sits alongside REPRO.yaml/discovery.md)
- **Date:** 2026-07-27

## Context

A model repo mixes two very different claims today: what the model *can* do
(supported platforms/backends, license, interfaces) and what was *actually
measured* (a benchmark result). Both currently leak into `model_card.json` and
prose. Conflating them lets a repo claim a platform is "supported" without any
result backing it — the "fake support" problem.

## Decision

Introduce **`rocmdoc.yaml`** — a *capability manifest* (`$def rocmdoc_manifest`).
It declares: `project`, `upstream`, `model`, `licenses`, `interfaces`, and
`implementations` (platform/backend/precision/interface/status). It is strictly a
**declaration of capability and intent**, never a benchmark result.

The load-bearing rule is **result alignment**, enforced by
`manifest.check_result_alignment`:

> A published `result_record` may NOT claim a platform+backend the manifest does
> NOT declare as `supported`/`experimental`. A result on a platform the manifest
> omits (or marks `planned`/`unsupported`) is a **fake-support violation** and is
> rejected.

A manifest backend of `""` (wildcard) declares the whole platform, so a manifest
need not enumerate every backend variant.

Manifest vs. result, sharply:

| | Manifest (`rocmdoc.yaml`) | Result (`result_record`) |
|---|---|---|
| Meaning | capability / intent | what was actually measured |
| Score | never | `metrics.overall` |
| Lives in | repo root | `model_card.json` v2 / evidence bundle |
| Check | schema + result alignment | schema + assurance + provenance |

`capabilities --json` from the standard CLI (ADR-0011) MUST agree with this
manifest; the bridge reads capabilities from it.

## Consequences

- "Supported" is now a declared, checkable surface; results cannot exceed it.
- A new platform lands in two steps: declare it in the manifest (status
  `planned`/`experimental`), then publish a result (which then aligns).

## Reversibility

- The manifest is additive; removing it drops only the alignment gate (results
  would then be unchecked against declared capability).
