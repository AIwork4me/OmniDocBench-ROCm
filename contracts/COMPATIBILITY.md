# ROCmDoc Compatibility & Versioning

> Companion to [`ROCMDOC_STANDARD.md`](ROCMDOC_STANDARD.md). Defines how the
> Standard's normative requirements map onto this repository's real artifacts,
> the SemVer policy, the deprecation windows for legacy representations, and the
> immutable contract-commit rules that model repositories must follow.
>
> Status: **Active**. Scope: central `OmniDocBench-ROCm` repo and all compatible
> model adapter repos.

## 1. Authoritative sources in this repo

The Standard (§3.4) names three sources of truth. Their concrete homes here:

| Standard source | Concrete artifact(s) in this repo |
| --- | --- |
| Capabilities / contract (`rocmdoc.yaml`) | `contracts/manifest.md`, `contracts/cli-contract.md`, `contracts/adapter.md`, `contracts/backend-policy.md`, `contracts/license-policy.md`; runtime in `engine/omnidocbench_rocm/manifest.py`, `cli_contract.py` |
| Result index / identity (`model_card_v2.json`) | `engine/omnidocbench_rocm/model_card_v2.py`, `run_spec.py`, `tracks.py`, `primary.py`; spec in `contracts/conformance.md` |
| Evidence bundle | `engine/omnidocbench_rocm/bundle_validator.py`, `assurance.py`, `source_import.py`; aggregate schema `contracts/artifact-schema.json` |

`contracts/ROCMDOC_STANDARD.md` is the **umbrella** normative document
(MUST/SHOULD/MAY). The sibling `contracts/*.md` files (`adapter.md`,
`backend-policy.md`, `cli-contract.md`, `conformance.md`, `discovery.md`,
`license-policy.md`, `manifest.md`) are its **detailed specifications** and
remain authoritative — they are **not** legacy. Only the items in §4 below are
legacy/deprecated.

## 2. Where schemas and profiles live (single source of truth)

The Standard's idealized `contracts/schemas/` and `contracts/profiles/` trees are
**not** materialized as a parallel file set in this repo. By design there is one
source of truth; creating a second standalone set would violate the Standard's
"no parallel authority" rule.

- **Aggregate JSON Schema:** `contracts/artifact-schema.json`
  - `$schema`: `https://json-schema.org/draft/2020-12/schema` (Draft 2020-12)
  - `$id`: `https://omnidocbench-rocm/schemas/artifact-schema.json`
  - Shipped to installed packages as `omnidocbench_rocm/data/artifact-schema.json`
    (see `[tool.setuptools.package-data]` in `pyproject.toml`).
- **Per-contract validators:** Python modules in `engine/omnidocbench_rocm/`
  (`schema.py`, `cli_contract.py`, `bundle_validator.py`, `model_card_v2.py`,
  `manifest.py`). These form the homogeneous SDK; the cross-language wire
  contract is the JSON Schema above (Standard §6).
- **Conformance profiles:** implemented in
  `engine/omnidocbench_rocm/conformance_profiles.py`:
  `base`, `runtime-core`, `benchmark-omnidocbench-v16`, `reproducible-score`
  (cumulative — Standard §9). `inference-reproduced` is a human / controlled-GPU
  attestation and is intentionally **not** an automated profile.

> When the Standard references `contracts/schemas/<name>.schema.json`, treat
> `contracts/artifact-schema.json` (plus the named Python validator) as that
> source. Do **not** create a second schema file set.

## 3. Commands (Standard §11 → real CLI)

The Standard names a generic `rocmdoc-conformance`. This repo exposes it through
the `omnidocbench-rocm` CLI (`omnidocbench-rocm = omnidocbench_rocm.cli:main`;
package version declared in `pyproject.toml`):

| Standard interface | Real command |
| --- | --- |
| `check --profile base` | `omnidocbench-rocm conformance` (structural) |
| `check --profile {runtime-core, benchmark-omnidocbench-v16, reproducible-score}` | `omnidocbench-rocm conformance-profiles <profile>` (behavioral) |
| `render-quality-status --check` | `omnidocbench-rocm generate-hub`; drift guard `omnidocbench-rocm check-drift --check` and registry `--check` |
| `audit-zone` | zone audit over registry / canonical store (`engine/omnidocbench_rocm/hub.py`, `registry.py`) |
| canonical import | `omnidocbench-rocm import-result` → `validate-import` → `review-result` → `generate-hub` |
| v1→v2 model-card migration | `omnidocbench-rocm migrate-model-card` |

`conformance-profiles` is retained as the compatible alias required by Standard
§11; any rename MUST NOT break existing flows.

## 4. Legacy / deprecated representations

| Legacy | Current | Status |
| --- | --- | --- |
| `badge-policy.md` tiers (`verified` / `community` / `community-wanted`) | `producer_assurance` + `platform_review` (Standard §8) | **Deprecated.** Retained only as a *lossy* projection for v1 cards and the legacy hub render. v2 cards use assurance directly; a model card MUST NOT carry a model-wide `badge`/`verified` field. |
| `model_card.json` (v1) | `model_card_v2.json` (result-identity v3, `run_spec_hash`) | **Deprecated.** Readable but maps to a deprecated representation. Migrate with `omnidocbench-rocm migrate-model-card`. |

Legacy representations are retained for at least one minor release (Standard §14).
A breaking contract change bumps `major`; a compatible addition bumps `minor`.
Result corrections preserve audit history — no silent score edits (Standard §10
QS-6).

## 5. Contract cohort & spec-lock (immutable-commit rule)

Model repositories MUST lock an immutable central commit plus a contract cohort
(Standard §5). The cohort this zone targets:

- contract release: `rocmdoc-contracts-0.4.0`
- conformance release: `rocmdoc-conformance-0.4.0`
- result identity: **v3** (`run_spec_hash = sha256(canonical_json(run_spec))`)

**Iron rule:** the locked commit MUST be a real, immutable commit that fully
carries the contract. `main`, a branch name, an uncommitted worktree, or a
floating package version MUST NOT serve as a lock. If the umbrella contract entry
(`ROCMDOC_STANDARD.md`) is not yet committed, then **no existing commit carries
it**; in that case model spec-locks MUST remain pointed at the last real
contract-bearing commit, and the convergence report MUST emit
`CENTRAL_CONTRACT_COMMIT_REQUIRED` until a human commits the central contract and
the locks are re-pointed. Tooling MUST NOT fabricate a SHA, and MUST NOT point a
lock at an uncommitted or floating ref.

## 6. Comparison-track immutability

OmniDocBench v1.6 is an **immutable comparison track** (Standard §7.2): bound to
an explicit upstream commit, dataset revision, page-set hash, scorer revision,
scoring protocol, and metric set. It MUST NOT follow upstream `main`. A future
v1.7 (or any differing page-set / scorer / metric set) is a **separate track** and
MUST NOT be merged into a v1.6 card or the v1.6 leaderboard. Third-party entries
join the v1.6 track only when every track field matches exactly; otherwise they
form their own track.

## 7. External repositories are first-class

Compliance depends only on the public Standard and evidence (Standard §12,
§13.1) — **not** on namespace or organization ownership. Any repository that
locks a compatible contract, passes conformance, and supplies lawful provenance
may be imported via `omnidocbench-rocm import-result`. The central importer
accepts only immutable `{repository, commit, result_id, artifact hashes}` and
never takes ownership of the source repository.
