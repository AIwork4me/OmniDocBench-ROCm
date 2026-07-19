# Migration Audit — OmniDocBench-AMD → OmniDocBench-ROCm

- **Date:** 2026-07-19
- **Auditor:** Claude (Staff Engineer)
- **Branch:** `refactor/omnidocbench-rocm`
- **Base:** `main` @ `1a5166f` (clean working tree)

This audit establishes the factual state of the repository **before** the
0.2.0 rebrand, so that the migration's doc/reality claims rest on evidence
rather than assumption. Findings are bucketed: **Implemented**, **Partial**,
**Design-only (documented but not in code)**, **Non-goal (this migration)**.

---

## 1. Repository state

- Repo path: `/workspace/omnidocbench-amd`
- Branch/HEAD: `main` @ `1a5166f`, clean.
- Remote: `https://github.com/AIwork4me/OmniDocBench-AMD.git`
- Last commits: `1a5166f docs: handoff …`; `3821d97 chore: rename repo references to OmniDocBench-AMD (brand); package/CLI/import stay lowercase`; `84b91e2 Merge pull request #1 from AIwork4me/feat/platform-foundation`.
- Baseline tests: 8 files, 466 lines, `python -m pytest -q` green.

## 2. Implemented (real, in code)

**Python package `engine/omnidocbench_amd/`** (to be renamed `omnidocbench_rocm/`):
- `__init__.py` — `__version__ = "0.1.0"`.
- `cli.py` — argparse CLI, `prog="omnidocbench-amd"`, subcommands `cdm`, `dataset`, `infer`, `score`, `publish`, `run`, `conformance`. `run --stage all` orchestrates download→infer→score→publish.
- `stages.py` — four-stage orchestrator (download → infer → score → publish); adapter invoked as subprocess (filesystem-decoupled); full-set enforcement (`limit_pages` must be null to publish).
- `types.py` — `AdapterConfig`, `PageStatus`, `RunSummary` (with `to_run_stats()`/`write()`/`from_run_stats()`; `schema_version: 1`).
- `schema.py` — loads `contracts/artifact-schema.json`, builds `Draft202012Validator` per `$def`; `validate_artifact(name, obj)`.
- `conformance.py` — `check_repo(repo)`; checks adapter, eval config, results dirs, README sections, `examples/`, `pyproject.toml` dependency (currently the literal `"omnidocbench-amd"`), `model_card.json` schema validity.
- `artifact_utils.py`, `_paths.py`, `download_omnidocbench.py`.
- `backends/base.py` (abstract `Backend`), `backends/linux_rocm.py` (`LinuxRocmBackend` — `score()` invokes `pdf_validation.py` in the eval-venv).

**Contracts `contracts/`**:
- `adapter.md` — canonical adapter contract (R1–R6).
- `artifact-schema.json` — JSON Schema draft 2020-12, `schema_version: 1`; `$defs`: `run_stats`, `provenance`, `run_summary`, `model_card`; `platform` enum `["linux-rocm", "windows-hip"]`; badge tiers `verified | community | community-wanted`.
- `badge-policy.md`, `conformance.md`.

**Hub `hub/registry.yaml`** — 3 models (`paddleocr-vl-1.6`, `unlimited-ocr`, `mineru2.5`), all `community-wanted`, `overall: null` on both platforms.

**Template `template/`** — full cookiecutter scaffold (default `repo_name: Model-AMD`, dep `omnidocbench-amd>=0.1.0`, CLI `omnidocbench-amd`), incl. adapter, eval config, examples, `model_card.json`, Makefile, READMEs, setup scripts.

**Scripts** — `scripts/check_conformance.py` (thin re-export of the engine checker), `scripts/generate_registry.py` (yaml loader + Markdown table renderer).

**Tests** — 8 files (466 lines): `test_artifact_utils`, `test_backends`, `test_cli`, `test_conformance`, `test_contract_integration`, `test_download`, `test_registry`, `test_schema`, `test_stages`, `test_template`. All green.

**CI** — `.github/workflows/ci.yml`, CPU-only, Python 3.11 only, runs pytest + conformance fixture + cookiecutter render.

## 3. Partial (implemented but incomplete)

- `backends/linux_rocm.py` — `score()` implemented; `provision_cdm()` is a no-op stub (prints a reference to a `cdm/setup-linux.sh` that does **not** exist); revision pinning hardcoded to `master`.
- `conformance.py` dependency check — naive substring match `"omnidocbench-amd" in pyproject.toml`.
- `artifact-schema.json` — carries `platform` + `badge` but no dimension separation (no `backend`/`execution_provider`/`backend_family`/`compatibility_status`/`target_backend`).

## 4. Design-only (documented as live, but NOT in code)

These are the doc/reality inconsistencies the 0.2.0 migration corrects:

1. **`backends/windows_hip.py` does not exist.** Yet `backends/__init__.py::get_backend("windows-hip")` lazy-imports `from .windows_hip import WindowsHipBackend`, which raises `ModuleNotFoundError` at call time. Documents (architecture.md) describe a working Windows backend. → Migration: make `get_backend("windows-hip")` raise an explicit `NotImplementedError`; docs say "planned/onboarding".
2. **`engine/omnidocbench_amd/cdm/` directory does not exist.** `architecture.md` and `adapter.md` reference `cdm/setup-linux.sh`, `cdm/setup.ps1` as live files. CDM exists only as a `print()` in `linux_rocm.py::provision_cdm`. → Migration: docs state CDM is a partial Linux scaffold, Windows planned; no fabricated toolchain.
3. **No Windows CDM toolchain** (`windows-cdm.patch`, `score.ps1`, `score-cdm.sh`, WSL boundary flow). `architecture.md` has a whole section describing it. → Migration: section removed.
4. **No MkDocs hub site** (no `mkdocs.yml`). `registry.yaml` and `generate_registry.py` docstrings reference one. → Migration: stated as "planned, not yet implemented".
5. **No GPU CI; no registry auto-sync.** → already honestly documented in `ci-reality.md`.

## 5. Non-goal (this migration)

- Implementing the Windows backend, CDM toolchain, MkDocs hub, GPU CI, or registry auto-sync.
- Modifying the OmniDocBench scorer algorithm or any public metric formula.
- Renaming the upstream benchmark `OmniDocBench`, the platform keys `linux-rocm`/`windows-hip`, the results path `results/omnidocbench/v16/<platform>/`, or the three model repos.
- Fabricating any eval result, or auto-promoting any `community`/`community-wanted` entry to `verified`.

## 6. Brand-residue inventory (pre-migration)

Forbidden tokens and their occurrence counts (whole-repo `grep -RIn`, excluding `.git`, `__pycache__`, `.pytest_cache`, `*.egg-info`):

| Token | Count | Treatment |
|---|---|---|
| `OmniDocBench-AMD` | 22 | rename → `OmniDocBench-ROCm` |
| `omnidocbench-amd` | 147 | rename → `omnidocbench-rocm` |
| `omnidocbench_amd` | 125 | rename → `omnidocbench_rocm` |
| `AMD Doc Parsing` | 5 | rename → `OmniDocBench-ROCm` |
| `Model-AMD` | 8 | rename → `Model-ROCm` |
| `omnidocbench-amd-windows` | 33 | references the deleted historical docs; removed from live docs |
| `DirectML` | 24 | retained (technical term; use governed by `backend-policy.md`) |
| `Vulkan` | 4 | retained as a term but removed from recommendations (out of scope) |
| `windows-hip` | 95 | **retained** (platform key) |
| `omnidocbench/` (path segment) | 46 | **retained** (upstream benchmark / results path) |

## 7. PyPI / downstream evidence (justifies dropping the legacy surface)

- `omnidocbench-amd` on PyPI → **HTTP 404** (never published).
- `omnidocbench-rocm` on PyPI → **HTTP 404** (name available).
- Downstream dependency check across the three model repos cloned locally:
  - `HunyuanOCR-ROCm` — string appears only in `docs/superpowers/*` and `reports/HANDOFF.md` (narrative), **not** as a pip dependency.
  - `MinerU-ROCm` — string appears only in `CONTRIBUTING.md`, `Makefile`, `README.md`, `NOTICE`, `CHANGELOG.md` (narrative), **not** as a pip dependency.
  - `Unlimited-OCR-ROCm` — **no references**.

**Conclusion:** `omnidocbench-amd` was never published and has no pip downstream consumers. Per the approved design (AD1 / ADR-0002), the legacy compatibility surface is dropped entirely in 0.2.0 — no shim module, no legacy console-script alias, no second PyPI distribution. The CI brand-residue gate replaces the would-be "legacy interface still works" checks.

## 8. Template Makefile bug (spec §VIII, confirmed)

`template/{{cookiecutter.repo_name}}/Makefile` defines a single shared rule
`eval-linux eval-windows:` that uses `PLATFORM ?= linux-rocm`, so
`make eval-windows` silently runs Linux. Fixed in Commit 4 by splitting into
two recipes with explicit `--platform` values, plus a regression test.
