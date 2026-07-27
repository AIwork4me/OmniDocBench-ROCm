# Standard CLI Contract

This contract defines the optional **standard CLI** a per-model adapter may
expose (ADR-0011). The central repo **defines and validates** it; it never
implements a model runtime and never imports `torch`/`vllm`/`paddle` — adapters
run as subprocesses (R1 of `adapter.md` is preserved). A model that only ships
`run_adapter.py` (the adapter-script interface) is still fully conformant; the
standard CLI is an *additional*, machine-checkable surface.

The canonical `parse` output is the `cli_result` `$def` of
`artifact-schema.json`. Machine-checkable behavior lives in
`omnidocbench-rocm conformance-profiles` + the fake-CLI fixtures.

## 1. Commands

```
<cli> version        --json
<cli> capabilities   --json
<cli> doctor         --json
<cli> parse --img-dir D --out-dir O --platform P [--backend B] [--benchmark X] --json
```

| Command | Output `$def` | Required fields |
|---|---|---|
| `version --json` | `cli_version` | `name`, `version` |
| `capabilities --json` | `cli_capabilities` | `platforms[]` (each `platform`+`backend`) |
| `doctor --json` | (loose) | `status` ∈ {`ready`,`not-ready`} |
| `parse ... --json` | `cli_result` | `schema_version`, `status`, `pages[]` |

`--json` means **print exactly one JSON document to stdout** — no log lines, no
banners. Any non-JSON noise is a CONTRACT violation (exit 4).

## 2. Exit codes (normative)

| Code | Name | Meaning |
|---|---|---|
| 0 | OK | full success |
| 1 | PARTIAL | run completed, some pages failed (per-page failures caught, run continued — R2) |
| 2 | USAGE | argument / misuse error |
| 3 | BACKEND_MISMATCH | requested `--backend` != the backend that actually ran |
| 4 | CONTRACT | stdout was not valid JSON or missed required fields |
| 5 | FATAL | uncaught crash / no output produced |

## 3. `parse` semantics

- One `<image_stem>.md` per page (R3); the CLI lists/sorts `--img-dir` itself.
- Per-page failure → recorded, run continues, **never raises** (R2). At least one
  failed page → `status: partial` + exit 1.
- `backend`/`engine` in the result is the **adapter-reported** backend (R-bridge);
  a mismatch with `--backend` → exit 3, never silently recorded.
- `page_count` must equal the number of images (full-set honesty).
- `full_set: true` only when the full set was processed (no `--limit`).

## 4. CLI → adapter bridge

A repo that only has `run_adapter.py` gains the standard CLI for free via the
bridge (no rewrite):

```bash
python -m omnidocbench_rocm.cli_bridge parse \
  --adapter adapter/run_adapter.py --img-dir imgs --out-dir out \
  --platform linux-rocm --backend vllm --json
```

The bridge subprocesses `run_adapter.py`, reads `_run_stats.json`, and emits a
`cli_result` with the correct exit code. `capabilities` is read from
`rocmdoc.yaml` (ADR-0009) when present.

## 5. Validation

```bash
omnidocbench-rocm conformance-profiles runtime-core --cli path/to/cli
omnidocbench-rocm conformance-profiles benchmark-omnidocbench-v16 --cli path/to/cli --img-dir imgs
```

Profiles are cumulative: `base` ⊂ `runtime-core` ⊂ `benchmark-omnidocbench-v16`.
`reproducible-score` checks a `result_record` (provenance + hashes).
