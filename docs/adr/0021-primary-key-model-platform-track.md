# ADR-0021: Primary key is (model_id, platform, comparison_track_id)

- **Status:** Accepted (Round-2 P0-6 reconciliation; maintainer decision 2026-08-01, Option A)
- **Date:** 2026-08-01

## Context

Standard §7.3 originally read "每个 `model_id + comparison_track_id` MUST 最多有一个 primary result" — at most one primary per (model, track). Taken literally, a multi-platform model with a legitimate best result on EACH platform violates the rule even though one-primary-per-platform is the intended, meaningful signal. The concrete case: MinerU2.5 carries `mineru2-5__linux-rocm__vlm-vllm…` (95.56) AND `mineru2-5__windows-hip__vlm-llamacpp…` (95.46), both `primary=True` on the same track `omnidocbench-v1-6-full-default-f23c37da`. Under the literal (model, track) key this is a "multiple primaries" violation; under one-primary-per-platform it is exactly right.

`registry.check` already keys primary-uniqueness on `(model_id, platform)` (ADR-0016, locked by `tests/test_primary_per_track.py`) for the multi-backend README/registry mirror. The track-level drift detector needed the same platform dimension, or it would false-positive on every multi-platform model.

## Decision

The primary-uniqueness key is **(model_id, platform, comparison_track_id)**: at most one primary per model, per platform, per comparison track.

- Standard §7.3 is updated to this wording.
- The `multiple-primaries-per-track` drift detector (`hub.check_drift`) keys on the same triple: a genuine per-platform primary is no longer flagged, while two primaries on the SAME (model, platform, track) still are.
- `registry.check`'s `(model_id, platform)` key is UNCHANGED and remains authoritative for the registry/README mirror; this ADR reconciles the track-level detector to the same platform-aware semantics.

## Consequences

- MinerU2.5's two primaries (linux + windows, full track) are legitimate — no drift finding.
- A model that nominates two primaries on the SAME platform+track is still flagged (the real ambiguity the rule exists to catch).
- This is a Standard-wording + detector reconciliation, recorded here rather than applied silently — `registry.check` is test-locked and is NOT changed by this ADR.
- The `primary_selection_record` (Standard §7.3) still requires `selected_by` / `selected_at` / `rationale` / `policy_version`; the key change does not relax the explicit-selection requirement.
