# ADR-0016: Comparison tracks + explicit primary selection

- **Status:** Accepted (Round-2 comparability correctness)
- **Date:** 2026-07-28

## Context

v2 (ADR-0012) listed every valid result in one table and implied they were
comparable. They are not: a full-set result next to a canary result next to a
paper number implies a false ranking. The `primary_result_id` was a free string
with no rule against "highest score wins".

## Decision

**Comparison tracks** (`tracks.py`, `$def comparison_track_record`): results are
compared **only within a track**. `track_id` is derived deterministically from
`(benchmark_id, benchmark_version, dataset_subset, scorer_protocol, extra)` plus
a short content-derived suffix.

```
track_id = "omnidocbench-v1-6-full-default-<8hex>"
```

Rules (enforced):

1. full vs canary ⇒ different tracks; different benchmark version ⇒ different;
   different scorer protocol ⇒ different; layout-only/table-only/full ⇒ different.
2. External paper/upstream/vendor results (`is_external_paper`) **never** enter a
   ROCm track (recorded as context only).
3. `superseded`/`retracted`/`invalid` are excluded from a track's DEFAULT view
   (`default_view`) but retained for history (never deleted).
4. A result with no `comparison_track_id` is a legacy result — excluded from the
   default leaderboard.
5. Track definitions are versioned; a content change yields a new `track_id`.

**Primary selection** (`primary.py`, `$def primary_selection_record`): an
explicit, auditable record `{model_id, comparison_track_id, result_id,
selected_by, selected_at, rationale, policy_version}`.

1. **Never** auto-pick-highest — there is deliberately no `pick_primary` helper
   anywhere in the codebase.
2. The selected result must be `valid` and belong to the named track.
3. `superseded`/`retracted`/`invalid` can never be primary.
4. With no primary, the Hub shows **all** valid results — it does not guess.

## Consequences

- No more false cross-track comparisons or "NVIDIA v1.5 vs ROCm v1.6" diffs.
- Primary is an honest, reviewable choice.

## Reversibility

- Additive: `comparison_track_id` / `comparison_tracks` / `primary_selection`
  are optional. v2 `primary_result_id` is still honored (`primary.primary_of`).
