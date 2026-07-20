# Badge Policy

Each per-model repo carries a per-platform badge in its `model_card.json`
(`badge.linux-rocm`, `badge.windows-hip`), drawn from three tiers. Badges are
assigned by maintainers; the `check_conformance` script is the gate for the
lower tier and a maintainer reproduction is the gate for the higher tier.

## Badge tiers

| Badge | Meaning | Requirements |
|-------|---------|--------------|
| `verified` | A maintainer reproduced the claimed result on this platform in a clean Docker environment. | 1. Passes `check_conformance` (CONFORMANT). 2. Maintainer ran the full OmniDocBench v1.6 eval on this platform in Docker and reproduced the committed `overall` score within tolerance. 3. A `VERIFIED.yaml` is committed at the repo root recording: maintainer, date, docker image, platform, reproduced overall, delta vs committed. |
| `community` | Provenance-complete and conforms, but not maintainer-reproduced. | 1. Passes `check_conformance` (CONFORMANT). 2. Committed `results/omnidocbench/v16/<platform>/` contains schema-valid `run_summary.json` + `provenance.json` (provenance-complete). 3. `model_card.json` validates against the schema. |
| `community-wanted` | No results submitted for this platform yet. | Used for the missing side when a repo only ships one platform. No `results/omnidocbench/v16/<platform>/` dir is declared. |

## Per-platform independence

Badges are per-platform and independent. A repo may be `verified` on
`linux-rocm` and `community-wanted` on `windows-hip` (or any combination). The
`platforms` array in `model_card.json` lists which platforms have any results;
the `badge` object records the tier for each.

## Promotion path

```
community-wanted  --[submit platform results + pass conformance]-->  community
community         --[maintainer Docker reproduction + VERIFIED.yaml]-->  verified
```

A repo that loses conformance (e.g. removes a required README section) is
demoted: `verified` -> `community` (conformance gate fails, VERIFIED.yaml
becomes stale) until re-verified; `community` -> `community-wanted` if results
are removed.

Tolerance is machine-checked by `scripts/check_verified.py`
(`|reproduced − committed| ≤ 0.5`). The reproduction runs in
`engine/omnidocbench_rocm/docker/Dockerfile.repro`, which is `FROM` OmniDocBench's
official verified image (`ghcr.io/zeng-weijun/omnidocbench-eval:repro-ubuntu2204`).
It reproduces **scoring** (Edit_dist + TEDS + CDM) from committed predictions,
pinning the exact toolchain for reproducibility. CDM also works on the host
(via the OmniDocBench checkout's `.venv`); Docker is for verified-repro pinning.

## `VERIFIED.yaml` shape

```yaml
model_id: <model>
platform: linux-rocm          # or windows-hip
maintainer: <github-handle>
date: YYYY-MM-DD
docker_image: <image:tag>
reproduced_overall: <number>
committed_overall: <number>
delta: <number>               # reproduced - committed (|delta| within tolerance)
tolerance: 0.5                # max acceptable |delta|
engine_version: <omnidocbench-rocm version>
git_commit: <repo commit verified>
```

## Gate summary

- `check_conformance` (exit 0) is the **hard gate** for both `community` and
  `verified`.
- A maintainer Docker reproduction + committed `VERIFIED.yaml` is the
  **additional gate** for `verified` only.
- `community-wanted` has no gate (it is the default for an absent platform).
