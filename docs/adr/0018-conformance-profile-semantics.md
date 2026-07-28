# ADR-0018: Conformance profile semantics (names must mean what they say)

- **Status:** Accepted (Round-2 correctness fix)
- **Date:** 2026-07-28

## Context

v2 conformance profiles were cumulative but their names lied:
`reproducible-score` only checked that artifact **hashes** were intact — it
never ran a scorer. The offline check only set an env flag without truly blocking
the network. And every profile either "passed" or "failed", with no way to say
"could not run" (e.g. a GPU profile under `RUN_GPU=false`).

## Decision

Adopt an explicit, programmatic ladder where each name means exactly what it
says (`conformance_profiles.py`):

```
base  <  runtime-contract  <  benchmark-contract  <  evidence-integrity
       <  score-reproduction  <  inference-reproduction  <  cross-hardware-reproduction
```

- `evidence-integrity` checks required files + schema + artifact hash + source
  reference + page count + `result_id` + `run_spec_hash` + requested/actual
  backend + identity + `producer_assurance`. It **does not** claim a score was
  replayed.
- `score-reproduction` **really** runs a fixed scorer over fixed predictions and
  diffs the metrics (`run_scorer_replay`). A fixture scorer is OK for CI but a
  fixture pass does **not** promote any result's `platform_review` — that is a
  separate review step.
- `inference-reproduction` / `cross-hardware-reproduction` require real AMD-GPU
  evidence; under `RUN_GPU=false` they are `NOT_RUN` (status `not-run`, `ok`
  stays False — **never reported as passed**).

Rules (enforced):

1. Profiles accumulate via an explicit dependency graph (`profile_includes` /
   `accumulate`), not just documentation.
2. v2 names are **aliases** (`runtime-core`→`runtime-contract`,
   `benchmark-omnidocbench-v16`→`benchmark-contract`,
   `reproducible-score`→`evidence-integrity`) so existing repos/tests are
   unaffected.
3. Offline hardening: `assert_no_network` monkeypatches `socket` for real on the
   central import/validate paths; CLIs honor the `ROCMDOC_NETWORK_DENY=1`
   convention (true socket blocking of an arbitrary subprocess needs a network
   namespace — a deployment concern).

## Consequences

- "Hash intact" is no longer reported as "score reproduced".
- GPU profiles are honestly `NOT_RUN`, not silently passed.

## Reversibility

- v2 profile names + `PROFILE_ORDER`/`PROFILES` are unchanged. Reverting removes
  the ladder + aliases.
