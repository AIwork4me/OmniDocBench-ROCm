# ADR-0011: Standard CLI contract + behavioral conformance

- **Status:** Accepted (extends the adapter contract, contracts/adapter.md; R1–R6 preserved)
- **Date:** 2026-07-27

## Context

The adapter contract (contracts/adapter.md) defines the `run_adapter.py`
*script* interface and structural conformance (`check_repo`). That conformance is
about files and shapes — it does not check how a model's CLI *behaves* at runtime
(pure JSON output, exit codes, backend honesty, partial-success handling). With
no AMD GPU in CI (docs/ci-reality.md), runtime behavior can only be checked
against a contract surface, not real inference.

## Decision

Define a **standard CLI contract** every conformant adapter may expose
(`cli_contract.py`, contracts/cli-contract.md): four JSON-emitting subcommands
and a fixed exit-code scheme.

```
<cli> version        --json     # identity
<cli> capabilities   --json     # declared platforms/backends/interfaces
<cli> doctor         --json     # readiness / offline check
<cli> parse <args>   --json     # parse pages -> canonical result.json
```

Exit codes (normative):

| Code | Name | Meaning |
|---|---|---|
| 0 | OK | full success |
| 1 | PARTIAL | run completed, some pages failed (never raised per-page — R2) |
| 2 | USAGE | argument / misuse error |
| 3 | BACKEND_MISMATCH | requested backend != the one that actually ran |
| 4 | CONTRACT | stdout not valid JSON / missed required fields |
| 5 | FATAL | uncaught crash / no output |

The canonical `parse` output is the `cli_result` `$def`. The central repo
**defines and validates** this contract; it never implements a model runtime and
never imports torch/vllm/paddle — adapters run as subprocesses (R1 preserved).

**Behavioral conformance profiles** (`conformance_profiles.py`) run a model's CLI
as a subprocess and check behavior, cumulatively:

| Profile | Checks |
|---|---|
| `base` | version --json works, valid `cli_version` |
| `runtime-core` | + capabilities + doctor --json, pure JSON, offline-capable, exit codes |
| `benchmark-omnidocbench-v16` | + full-set parse on v1.6, valid `cli_result`, backend match |
| `reproducible-score` | provenance-complete + artifact hashes valid (on a result_record) |

Profiles run in CI against **fake-CLI fixtures** (`tests/fixtures/fake_cli/`:
success / partial / fatal / badjson / backend_mismatch) — no GPU, no runtime
imported. Real adapters gain the standard CLI via the `cli_bridge` shim
(`python -m omnidocbench_rocm.cli_bridge`), which wraps a legacy `run_adapter.py`
and preserves R1–R6 + the backend-mismatch gate.

## Consequences

- "Conformant" now means *behaves* correctly, not just *looks* correct.
- The central repo stays runtime-free; validation is subprocess-based.
- A model repo can adopt the standard CLI incrementally (bridge now, native later).

## Reversibility

- The contract and profiles are additive; the bridge is opt-in. Removing them
  leaves the original adapter-script contract fully intact.
