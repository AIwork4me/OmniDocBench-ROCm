# ADR-0003: Trust bar — listing floor, verified apex, and completeness

- **Status:** Accepted
- **Date:** 2026-07-23

## Context

The zone's reason to exist is developer trust earned through rigorous,
complete, reproducible evaluation — not "it ran a demo." The trust ladder
(`community-wanted` → `community` → `verified`) and the scoring-repro gate
are already defined in [`contracts/badge-policy.md`](../../contracts/badge-policy.md)
and explained in [`docs/ci-reality.md`](../ci-reality.md). Three questions
remained open and are decided here:

1. **Listing floor.** `hub/registry.yaml` currently lists models with no
   committed result (`community-wanted`, `overall: null`) *inside* the
   comparison table. Under the trust premise, an entry with no rigorous eval
   does not earn a place in a comparable row.
2. **Apex reproduction depth.** `verified` today reproduces *scoring* from
   committed predictions in pinned Docker. Should the apex additionally
   require a maintainer to re-run each model's *inference* on AMD hardware?
3. **What "complete" means.** The headline today is a single `overall`; what
   else must a trustworthy entry disclose?

## Decision

**Floor.** A model appears in the **comparison table** only at `community` or
above (a committed, full-set, provenance-complete result). Models with no
committed result for a platform appear in a separate **incoming /
community-wanted lane** — preserving the contributor-recruitment signal
without presenting an unscored model as comparable. `hub/registry.yaml`
remains the source of truth for both; the renderer
(`scripts/generate_registry.py` and the future MkDocs site) splits them by
badge tier.

**Apex.** `verified` = scoring-repro in pinned Docker (`Dockerfile.repro`,
`|reproduced − committed| ≤ 0.5` via `scripts/check_verified.py`) **plus a
committed, anyone-can-run reproduction recipe**. The recipe is a new,
environment-portable artifact **distinct from the existing audit-only
`provenance.adapter_command`** — which [`architecture.md`](../architecture.md)
already notes is "an audit record of what ran, not a reproduction recipe."
The recipe records the exact pasteable command, the pinned model-weights
revision, the backend, and the venv/Docker, so a sceptic with AMD hardware can
regenerate the predictions themselves.

The apex is **not** raised to require a maintainer re-run of inference, and is
**not** coupled to a self-hosted GPU runner — both are explicitly deferred
(see Reversibility).

Rationale for stopping at scoring-repro + recipe rather than inference-repro:
scoring is deterministic given the predictions + toolchain, whereas inference
is noisy across ROCm/driver/hardware, so a numeric tolerance on inference
would be arbitrary. Trust that the predictions genuinely came from the model
rests on *detectability* (anyone can re-run the recipe and expose a
mismatch), not on a maintainer re-running every model. This is the same
posture as paper-with-code review without per-submission GPU re-runs.

**Completeness ("全亮").** A trustworthy entry discloses, all committed and
rendered on the hub:

- the **full set** (`limit_pages` must be `null` to publish — already enforced);
- **CDM**, mandatory (a valid score, or an honest `pending`/zero — never faked);
- a **per-category breakdown** (formula / table / text / layout) — the category
  data already exists in `metric_result.json`, so this is a presentation
  requirement, not new computation;
- **efficiency metrics**: latency (s/page), peak VRAM, and the GPU the result
  ran on. This is new: the artifact schema and `run_summary.json` gain an
  efficiency section, fed by the adapter via `_run_stats.json`.

## Consequences

- The registry renderer must separate the comparison table from the incoming
  lane. The two currently-`community-wanted` reference models (`unlimited-ocr`,
  `hunyuan-ocr`) move to the incoming lane on any platform where they have no
  committed result, until they reach `community`.
- Each model repo gains a committed **reproduction recipe** artifact as a
  `verified` prerequisite; its name/location is fixed in
  [`contracts/conformance.md`](../../contracts/conformance.md).
- The artifact schema extends with an efficiency section;
  [`contracts/adapter.md`](../../contracts/adapter.md) gains an
  efficiency-reporting requirement on the adapter.
- Inference is deliberately **not** gated on a numeric tolerance. This is
  recorded so a future contributor does not "tighten" the apex by demanding
  inference-repro — that path is a known, deferred option, not the current bar.

## Reversibility

- **Floor / completeness:** low cost to adjust (renderer + schema changes).
- **Apex depth:** *not* raising to inference-repro keeps the apex achievable
  and decoupled from "does a working backend exist on maintainer hardware
  today." A **self-hosted AMD GPU runner** that auto-reproduces the reference
  models on release is the natural future strengthening — recorded here as a
  known, deferred option, to be re-decided when the catalog and maintainer
  bandwidth justify the infra.
