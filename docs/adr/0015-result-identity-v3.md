# ADR-0015: Result identity v3 (run_spec + run_spec_hash)

- **Status:** Accepted (Round-2 identity correctness)
- **Date:** 2026-07-28

## Context

v2 identity (`model_card_v2.make_result_id`) derived a `result_id` from only
`(model, platform, backend, precision, benchmark_version)` and **masked** a
missing backend/precision as the literal `"default"`. Consequences: (a) two
scientifically-different runs could collapse to one id; (b) the central platform
fabricated `default/default` results no sub-repo produced (the drift Round-2
kills); (c) scorer/dataset/weights changes did not change identity.

## Decision

Derive identity from the **full run specification** (`run_spec.py`):

```
run_spec = {model, implementation, benchmark, inference}
run_spec_hash = sha256(canonical_json(run_spec))        # full 256-bit
result_id_v3  = "<model-slug>-<benchmark-slug>-<short16hex>"
```

`canonical_json` sorts dict keys recursively (list order is preserved — it is
scientifically meaningful, e.g. a multi-GPU topology). The 16-hex short suffix is
collision-safe for the current dataset scope; the **full** sha256 is stored in
`run_spec_hash`.

Rules (enforced in `run_spec.py`):

1. Same `run_spec` → same hash → same id (deterministic, reproducible).
2. Any scientifically-material change (precision, weights_revision, prompt_hash,
   scorer_revision, components, …) → a new hash → a new id.
3. A genuinely-unknown value MUST be the literal `"unknown"` — never masked as
   `"default"`. The `default` sentinel is forbidden for `backend`/`precision`
   (`uses_default_sentinel`).
4. `missing_critical` / `insufficient_identity` flag results missing critical
   fields (or carrying `unknown`) — such results are well-formed but barred from
   the default comparison table (never auto-promoted).
5. Legacy v2 `result_id`s are preserved verbatim in `legacy_result_ids[]`;
   migration records the legacy→new mapping; nothing is silently overwritten.

## Consequences

- The central `default/default` anti-pattern is now detectable (`check-drift`
  `default-default-identity`) and rejectable by `evidence-integrity`.
- Identity changes when the science changes; stable otherwise.
- Legacy identity remains traceable.

## Reversibility

- Additive: `run_spec` / `run_spec_hash` / `result_id_v3` / `legacy_result_ids`
  are optional on `result_record`. v2 `make_result_id` is unchanged. Reverting
  drops the v3 layer.
