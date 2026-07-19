# Design: OmniDocBench-ROCm 0.2.0 transition

- **Date:** 2026-07-19
- **Status:** Approved (design) — pending spec review, then implementation plan
- **Author:** Claude (Staff Engineer, brand + architecture upgrade)
- **Scope:** One coherent migration, shipped as 6 reviewable commits on `refactor/omnidocbench-rocm`
- **Supersedes:** the deleted `2026-07-12-amd-doc-parsing-platform-foundation-*` design/plan/handoff (those stale AMD-era docs are removed as part of this transition — clean break)

---

## 1. Context & motivation

The platform repo is currently branded **OmniDocBench-AMD** (product), **omnidocbench-amd** (PyPI dist — never published), **omnidocbench_amd** (Python package), with the program name **"AMD Doc Parsing" zone**. v0.1.0 shipped a working Linux-ROCm eval engine, a cookiecutter template, contracts, and an honest placeholder registry.

The long-term boundary of this project is the **AMD ROCm open-source compute software stack** (HIP, MIGraphX, ONNX Runtime MIGraphX EP, PyTorch-ROCm, vLLM-ROCm, llama.cpp-HIP). The "AMD" brand conflates the company with the software stack and blurs the boundary against non-ROCm backends (DirectML, Vulkan, OpenVINO). This transition rebrands the project to **OmniDocBench-ROCm** to make the software-stack boundary explicit, and corrects documentation that over-states what is implemented.

### Audit findings (the facts this design rests on)

Repo at HEAD `1a5166f` on `main`, clean. Full audit is written to
`docs/audits/2026-07-omnidocbench-rocm-migration-audit.md` in commit 1. Summary:

**Implemented (production):**
- `engine/omnidocbench_amd/` — CLI (`cdm`/`dataset`/`infer`/`score`/`publish`/`run`/`conformance`, `prog="omnidocbench-amd"`), `stages.py` (download→infer→score→publish), `types.py` (`RunSummary`/`AdapterConfig`/`PageStatus`), `schema.py`, `conformance.py`, `artifact_utils.py`, `_paths.py`, `download_omnidocbench.py`, `backends/{base,linux_rocm}.py`.
- `contracts/` — `adapter.md`, `artifact-schema.json` (v1; `$defs`: run_stats/provenance/run_summary/model_card; platform enum `[linux-rocm, windows-hip]`; badge tiers verified/community/community-wanted), `badge-policy.md`, `conformance.md`.
- `hub/registry.yaml` — 3 models (PaddleOCR-VL-1.6, Unlimited-OCR, MinerU2.5), all `community-wanted`, `overall: null`.
- `template/` — full cookiecutter scaffold (default `repo_name: Model-AMD`, dep `omnidocbench-amd>=0.1.0`, CLI `omnidocbench-amd`).
- `tests/` — 8 files, 466 lines (baseline `pytest -q` green).
- `.github/workflows/ci.yml` — minimal CPU CI (Py 3.11 only).

**Partial:** `linux_rocm.py` — `score()` implemented; `provision_cdm()` is a no-op stub ("Task 14"); revision hardcoded to `master` ("Task 16"). `conformance.py` dependency check is a naive substring `"omnidocbench-amd" in pyproject.toml`.

**Design-only / does NOT exist (but documentation claims it does):**
1. `backends/windows_hip.py` — does not exist; yet `get_backend("windows-hip")` lazy-imports it → `ModuleNotFoundError` bomb.
2. `engine/omnidocbench_amd/cdm/` directory — does not exist; `architecture.md` + `adapter.md` reference `cdm/setup-linux.sh`, `cdm/setup.ps1` as live files. CDM exists only as a print statement in `linux_rocm.py`.
3. Windows CDM toolchain (`windows-codm.patch`, `score.ps1`, `score-cdm.sh`) — does not exist; `architecture.md` has a whole "Windows / WSL boundary (absorbed)" section describing it.
4. No MkDocs hub site (no `mkdocs.yml`); no GPU CI; no registry auto-sync.

**PyPI / downstream (decisive for §5):** `omnidocbench-amd` → **404, never published**; `omnidocbench-rocm` → **404, name available**. The three ROCm model repos (`HunyuanOCR-ROCm`, `MinerU-ROCm`, `Unlimited-OCR-ROCm`) do **not** pip-depend on this package — the string appears only in narrative docs. **No real downstream consumers.**

**Brand residue:** `OmniDocBench-AMD`×22, `omnidocbench-amd`×147, `omnidocbench_amd`×125, `AMD Doc Parsing`×5, `Model-AMD`×8 (incl. `tests/test_template.py`). Legitimately retained: `windows-hip`×95 (platform key), `omnidocbench/`×46 (upstream/results path). `DirectML`×24, `Vulkan`×4 (repositioned transitional / out-of-scope). `omnidocbench-amd-windows`×33 (references the deleted historical docs).

---

## 2. Goals, non-goals, out of scope

### Goals
- Rebrand product/repo → **OmniDocBench-ROCm**; Python dist → **omnidocbench-rocm**; package → **omnidocbench_rocm**; CLI → **omnidocbench-rocm**; template default → **Model-ROCm**.
- Define and enforce the ROCm backend policy (first-class / DirectML transitional / out-of-scope) in a versioned contract.
- Correct every doc/reality inconsistency: no fabricated Windows backend, no fabricated CDM toolchain, honest Current Status everywhere.
- Upgrade the template (correct Makefile platform bug, new defaults), registry (add validation, keep honest placeholder), CI (matrix + quality gates + brand-residue gate), and add the standard governance file set.
- Ship as clean, reviewable, logically-ordered commits; push branch + open PR. Remote GitHub rename stays gated behind green CI.

### Non-goals (explicitly NOT done in this transition)
- Do **not** modify the upstream OmniDocBench scorer algorithm or any public metric formula.
- Do **not** change `OmniDocBench` (upstream benchmark name) or the existing model-repo names (`HunyuanOCR-ROCm`, `PaddleOCR-VL-ROCm`, `MinerU-ROCm`).
- Do **not** fabricate a Windows backend, CDM toolchain, or any eval result. Do **not** auto-promote any `community`/`community-wanted` result to `verified`.
- Do **not** claim MIGraphX is production-ready on Windows, or fabricate any AMD/ROCm/ONNX Runtime roadmap or release date.
- Do **not** batch-modify other model repos. Do **not** delete historical eval results.
- Do **not** bump the artifact `schema_version` for the rebrand (only optional, backward-compatible fields are added).
- Do **not** rewrite git history (deleted files remain in history; this is honest and intentional).

### Out of scope (defined by the backend policy, §6)
Vulkan, OpenVINO, and any non-ROCm general GPU backend are out of scope as first-class project backends. DirectML is permitted only as a *temporary Windows compatibility fallback*.

---

## 3. Strategic boundary (the ROCm backend policy)

A new contract `contracts/backend-policy.md` (+ `contracts/backend-policy.zh-CN.md`) defines:

**First-class ROCm backends:** HIP Runtime / HIP SDK · MIGraphX · ONNX Runtime MIGraphX Execution Provider · PyTorch-ROCm · vLLM-ROCm · llama.cpp-HIP.

**Transitional backend:** DirectML — permitted *only* on Windows where an equivalent ROCm/MIGraphX capability is not yet available. DirectML use must satisfy six conditions (model doc labels it `compatibility fallback`; no "ROCm-native" badge; provenance records the real execution provider; results never described as MIGraphX/ROCm-EP; future target backend recorded as MIGraphX; enters deprecated→removed once a real ROCm path exists). The contract states explicitly that Windows MIGraphX is **not** currently production-ready and quotes no roadmap date.

**Out of scope:** Vulkan, OpenVINO, general non-ROCm GPU backends.

**Platform keys are frozen:** `linux-rocm` and `windows-hip` stay. Windows is **not** renamed to `windows-rocm` (the technical entry point is still the HIP SDK, and HIP is part of ROCm).

### Dimension separation
A single `platform` string used to carry platform + OS + runtime + execution-provider + compatibility-status. These dimensions are now separated via **optional, backward-compatible schema fields** (§7), while `platform` retains only its platform-key role.

---

## 4. Brand mapping

| Dimension | Old | New |
|---|---|---|
| Product / GitHub repo | OmniDocBench-AMD | **OmniDocBench-ROCm** |
| PyPI distribution | omnidocbench-amd (never published) | **omnidocbench-rocm** |
| Python package | omnidocbench_amd | **omnidocbench_rocm** |
| CLI | omnidocbench-amd | **omnidocbench-rocm** |
| Template default repo | Model-AMD | **Model-ROCm** |
| Program name | "AMD Doc Parsing" zone | **OmniDocBench-ROCm** platform |

**Frozen / unchanged:** `OmniDocBench` (upstream benchmark); the 3 model repos; platform keys `linux-rocm`, `windows-hip`; results path `results/omnidocbench/v16/<platform>/`; the scoring algorithm and every committed metric.

---

## 5. Architecture decisions

### AD1 — Package / CLI rename; legacy surface dropped (no compatibility shim)
Rename `engine/omnidocbench_amd/` → `engine/omnidocbench_rocm/`; update every internal `import omnidocbench_amd` → `omnidocbench_rocm`; `__version__ = "0.2.0"`; CLI `prog="omnidocbench-rocm"`.

`pyproject.toml`: `name = "omnidocbench-rocm"`, `version = "0.2.0"`, console-script `omnidocbench-rocm = "omnidocbench_rocm.cli:main"`, hatchling `packages = ["engine/omnidocbench_rocm"]`, force-include `contracts/artifact-schema.json`.

**No legacy compatibility shim.** There is no `omnidocbench_amd` import module, no `omnidocbench-amd` console-script alias, and no second PyPI distribution. **Justification (recorded in the audit + ADR-0002):** `omnidocbench-amd` was never published to PyPI (404) and has no pip downstream consumers (verified across the three model repos). Per spec §IV's evidence-gated simplification clause, the compatibility surface is dropped entirely. This removes dual-maintenance, the 0.3.0 removal cliff, and user confusion. The CI gate for the legacy interface (§9) is replaced by a **brand-residue gate** that forbids the old brand everywhere except the sanctioned record files (§8).

`from omnidocbench_rocm.types import RunSummary` and `omnidocbench_rocm.__version__` are the public surface (both already work structurally).

### AD2 — Backend policy + schema evolution (v1 preserved)
Schema `artifact-schema.json` keeps `schema_version: 1`. **Optional, backward-compatible fields** are added to the `model_card` and `provenance` `$defs`: `backend`, `execution_provider`, `backend_family`, `compatibility_status`, `target_backend`. `platform` enum stays `["linux-rocm", "windows-hip"]`. The validator continues to validate all existing v1 artifacts (no v2, no migration test needed). `$id` → `https://omnidocbench-rocm/schemas/artifact-schema.json` (non-resolving-URI style preserved).

### AD3 — Doc/reality honesty (no fabricated capabilities)
- **`get_backend("windows-hip")`** raises an explicit `NotImplementedError("windows-hip backend is planned/onboarding, not yet implemented; see contracts/backend-policy.md")` instead of the current silent `ModuleNotFoundError` lazy-import bomb. No stub backend, no fake scoring.
- **`architecture.md` rewritten** to match code: Linux-ROCm backend = implemented (score path real, CDM = partial stub); Windows-HIP = planned/onboarding; CDM toolchain = Linux stub now, Windows planned. The fabricated "Windows/WSL boundary", `cdm/setup-*.sh`, and `score.ps1` sections are removed. Topology uses `Model-ROCm/`.
- **`ci-reality.md`** stays honest; brand update only; the aspirational "windows-hip engine self-test" maintainer-test row is marked **planned** or removed.
- **`contracts/adapter.md` R6** keeps `linux-rocm → onnxruntime-rocm (ROCm EP)`; reframes the Windows row as "DirectML compatibility fallback (target: MIGraphX/ROCm EP when available)"; **Vulkan removed from the VLM recommendation** (named only in the out-of-scope sense).
- READMEs (EN + zh-CN) rewritten per the 15-section structure with an honest Current Status (Linux-ROCm implemented; Windows-HIP planned; registry = initial placeholder, not a leaderboard; 3 models pending onboarding).
- All stale AMD-era design/planning docs **deleted** (§10); inbound cross-references to them (e.g. `adapter.md` "Spec reference" line, README "Spec:" line) are removed/rewritten.

### AD4 — Template + Makefile
- `cookiecutter.json`: `repo_name = "Model-ROCm"`; template `pyproject.toml`: `dependencies = ["omnidocbench-rocm>=0.2.0"]`; all CLI refs → `omnidocbench-rocm`; GitHub URLs → `https://github.com/AIwork4me/OmniDocBench-ROCm`; `model_card.json` updated to the new optional fields + ROCm brand; smoke backend stays CPU-only; DirectML appears only in a Windows compatibility-fallback doc; Vulkan not recommended.
- **Makefile fix (spec §VIII):** `eval-linux` and `eval-windows` become **two separate recipes** that pass `--platform linux-rocm` and `--platform windows-hip` explicitly — no shared `PLATFORM ?= linux-rocm` default that silently runs Windows on Linux. New `tests/test_makefile_targets.py` asserts each target resolves to the correct platform (recipe inspection / dry-run parse).

### AD5 — Registry: honesty + validation
`hub/registry.yaml` keeps its honest placeholder state (3 models, `community-wanted`, `overall: null`); rebranded only. New `scripts/validate_registry.py` (wired into CI and the generator) checks: `model_id` present; `repo` well-formed `owner/name`; platform keys present; badge enum; `overall` type (number|null); **duplicate `model_id`**; illegal repo name; missing platform data. README explicitly states the registry is an initial placeholder, not a complete leaderboard. No unverifiable scores are added; no badge is auto-promoted.

### AD6 — CI matrix + quality gates + brand-residue gate
`.github/workflows/ci.yml` with `permissions: contents: read`, matrix **Python 3.10 / 3.11 / 3.12**, covering: `pytest` · `import omnidocbench_rocm` · `omnidocbench-rocm --help` · conformance fixture · cookiecutter render **+ rendered-project install + smoke demo** · registry validation · `python -m build` · wheel/sdist metadata sanity · README link / key-local-path check · **brand-residue gate** (`scripts/check_brand.py`, §8). No GPU jobs; untrusted PR code never reaches a long-lived GPU runner (none exists anyway).

### AD7 — Governance + ADRs + audit
New files: `CHANGELOG.md` (`0.2.0 — OmniDocBench-ROCm transition`), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `CITATION.cff`, `CODEOWNERS`, `.github/ISSUE_TEMPLATE/*`, `.github/PULL_REQUEST_TEMPLATE.md`, `docs/governance.md`, `docs/roadmap.md`, `docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`, `docs/adr/0001-rocm-project-boundary.md`, `docs/adr/0002-package-and-cli-migration.md`. (No `docs/migration-from-omnidocbench-amd.md` — the migration note is dropped; the CHANGELOG entry is the only forward pointer.)

---

## 6. Schema change detail (the only data-structure touch)

`contracts/artifact-schema.json`, `model_card` and `provenance` `$defs` — additions only:

```jsonc
// added to model_card.properties and provenance.properties (all optional):
"backend":              { "type": "string" },          // vllm-rocm | migraphx | onnxrt-migraphx | llama-cpp-hip | smoke | ...
"execution_provider":   { "type": "string" },          // ROCMExecutionProvider | DmlExecutionProvider | ...
"backend_family":       { "type": "string" },          // rocm | directml-fallback
"compatibility_status": { "type": "string" },          // first-class | transitional-fallback
"target_backend":       { "type": "string" }           // migraphx (for DirectML-fallback rows)
```

`schema_version` stays `1` everywhere. No existing artifact is invalidated. The validator (`engine/omnidocbench_rocm/schema.py`) is unchanged in behavior — jsonschema accepts new optional keys against the existing `$defs`.

---

## 7. File manifest

### Created (new)
- `contracts/backend-policy.md`, `contracts/backend-policy.zh-CN.md`
- `docs/audits/2026-07-omnidocbench-rocm-migration-audit.md`
- `docs/adr/0001-rocm-project-boundary.md`, `docs/adr/0002-package-and-cli-migration.md`
- `docs/governance.md`, `docs/roadmap.md`
- `CHANGELOG.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `CITATION.cff`, `CODEOWNERS`
- `.github/ISSUE_TEMPLATE/` (bug, feature, model-onboarding), `.github/PULL_REQUEST_TEMPLATE.md`
- `scripts/check_brand.py`, `scripts/validate_registry.py`
- `tests/test_makefile_targets.py`, `tests/test_brand_residue.py` (or fold brand check into CI script + a thin test)

### Modified (rename / rebrand / fix)
- `pyproject.toml` (name, version, scripts, packages)
- `engine/omnidocbench_amd/` → **`engine/omnidocbench_rocm/`** (all modules: `__init__.py`, `cli.py`, `stages.py`, `types.py`, `schema.py`, `conformance.py`, `artifact_utils.py`, `_paths.py`, `download_omnidocbench.py`, `backends/{__init__,base,linux_rocm}.py`) — internal imports + `prog` + `get_backend("windows-hip")` honest error
- `contracts/{adapter,badge-policy,conformance}.md` (rebrand + R6 Vulkan/DirectML fix + remove dead spec references)
- `contracts/artifact-schema.json` (`$id`, optional fields)
- `hub/registry.yaml` (comments/branding only — data unchanged)
- `scripts/check_conformance.py`, `scripts/generate_registry.py` (rebrand; conformance dependency check → `omnidocbench-rocm`)
- `template/cookiecutter.json`, `template/{{cookiecutter.repo_name}}/{pyproject.toml,Makefile,README.md,README.zh-CN.md,model_card.json,docs/backends.md,…}` (defaults, dep, CLI, URLs, Makefile platform fix, DirectML-only-in-fallback-doc)
- `README.md`, `README.zh-CN.md` (full rewrite)
- `docs/{architecture,ci-reality,contribute-a-model,contribute-a-model.zh-CN,pitfalls}.md` (rebrand + reality correction)
- `.github/workflows/ci.yml` (matrix + gates + brand check + permissions)
- `tests/{test_template,test_cli,test_conformance,test_backends,test_registry,test_schema,test_stages,test_artifact_utils,test_contract_integration,test_download}.py` (rebrand; `test_template.py` default assertion → `Model-ROCm`)
- `conftest.py` (comment rebrand if it references old name)

### Deleted (stale AMD-era design/planning docs — clean break)
- `docs/superpowers/specs/2026-07-12-amd-doc-parsing-platform-foundation-design.md`
- `docs/superpowers/plans/2026-07-12-amd-doc-parsing-platform-foundation.md`
- `docs/superpowers/HANDOFF-phaseA-paddleocrvl-onboarding-2026-07-12.md`

---

## 8. Brand-residue gate

`scripts/check_brand.py` enforces that the **product / user-facing surface** is clean of the old brand. It greps the repo for the forbidden tokens — `OmniDocBench-AMD`, `omnidocbench-amd`, `omnidocbench_amd`, `AMD Doc Parsing`, `Model-AMD`, `omnidocbench-amd-windows` — and fails on any hit that is not in an **internal-record exclusion set**.

**Excluded paths** (internal engineering records, never user-facing product material — they legitimately discuss the rename):
- `docs/superpowers/**` — this design spec, the implementation plan, future process docs.
- `docs/audits/**` — the migration audit must enumerate the old strings as evidence.
- `docs/adr/**` — ADRs record decisions, including why the old name was dropped.
- `CHANGELOG.md` — records "Renamed from OmniDocBench-AMD to OmniDocBench-ROCm".

**Everything else must be clean** — `README.md`, `README.zh-CN.md`, `engine/**`, `contracts/**` (incl. `artifact-schema.json`), `template/**`, `hub/**`, `scripts/**`, `tests/**`, `conftest.py`, `pyproject.toml`, `.github/**`, `Makefile`, `docs/{architecture,ci-reality,contribute-a-model*,pitfalls,governance,roadmap}.md`.

`DirectML` and `Vulkan` are **not** forbidden tokens — they are legitimate technical terms whose *use* is constrained by `contracts/backend-policy.md` (DirectML = transitional fallback only; Vulkan = out-of-scope), not blanket-banned.

`windows-hip` (platform key) and the path segment `omnidocbench/` (upstream benchmark / results path) are **retained by design** and are not scanned.

---

## 9. Commit plan (6 commits on `refactor/omnidocbench-rocm`)

1. **`docs: define OmniDocBench-ROCm scope and migration`** — audit doc, ADR-0001, ADR-0002, `contracts/backend-policy.md`(+zh), delete the 3 stale superpowers docs, fix inbound references to them.
2. **`refactor: rename package and CLI to omnidocbench-rocm`** — `engine/omnidocbench_amd/`→`omnidocbench_rocm/`, `pyproject.toml`, all internal imports, `prog`, `__version__`, schema `$id`, `scripts/*`, tests rebrand.
3. **`refactor: drop legacy omnidocbench-amd surface; conformance requires omnidocbench-rocm`** — conformance dependency check switched to `omnidocbench-rocm` (no legacy accept-path); explicit `NotImplementedError` for `windows-hip`; `check_brand.py` + `test_brand_residue`. *(Repurposed from the spec's "add legacy aliases" — aliases are dropped per AD1.)*
4. **`refactor: migrate contracts, schema, and templates to ROCm`** — `artifact-schema.json` optional fields; `contracts/*.md` rebrand + R6 fix; cookiecutter defaults/dep/CLI/URLs/`model_card.json`; **Makefile `eval-linux`/`eval-windows` split + `test_makefile_targets.py`**; template docs (DirectML fallback-only, no Vulkan rec).
5. **`ci: expand ROCm migration and package quality gates`** — `ci.yml` matrix + all gates + `permissions: contents: read`; `validate_registry.py` + registry CI; governance files (CHANGELOG, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, CITATION, CODEOWNERS, ISSUE_TEMPLATE, PR_TEMPLATE).
6. **`docs: complete ROCm project documentation`** — READMEs (full rewrite), `architecture.md` reality rewrite, `ci-reality.md`/`contribute-a-model*`/`pitfalls.md` rebrand, `governance.md`, `roadmap.md`.

Each commit is independently buildable and testable where feasible; the branch is green at the tip.

---

## 10. Verification (Phase 5) — real output recorded

```bash
python -m pytest -q
python -m build
python -m pip install --force-reinstall dist/*.whl
omnidocbench-rocm --help
python -c "import omnidocbench_rocm; print(omnidocbench_rocm.__version__)"
python scripts/check_conformance.py tests/fixtures/conformant
python scripts/check_brand.py                       # brand-residue gate
python scripts/validate_registry.py hub/registry.yaml
cookiecutter template --no-input --output-dir /tmp/omnidocbench-rocm-template
# rendered-project Makefile platform assertions + smoke
```

(Legacy `omnidocbench-amd --help` / `import omnidocbench_amd` checks are **absent by design** — that surface no longer exists.) All command output is captured into the final delivery report.

---

## 11. Git, PR, and remote rename (gated)

- Branch `refactor/omnidocbench-rocm` (created) carries all 6 commits.
- **Push branch + open PR** (account `AIwork4me`) once local Phase 5 is green. PR title: `refactor: upgrade platform to OmniDocBench-ROCm`.
- **Remote GitHub rename is gated** behind green CI on the PR and an explicit user go. Prepared (not run):
  ```bash
  gh repo rename OmniDocBench-ROCm --repo AIwork4me/OmniDocBench-AMD --yes
  git remote set-url origin https://github.com/AIwork4me/OmniDocBench-ROCm.git
  ```
  Post-rename: verify `git remote -v`, `gh repo view AIwork4me/OmniDocBench-ROCm`, and that the old URL `https://github.com/AIwork4me/OmniDocBench-AMD` redirects. A pre-rename checklist is delivered with the final report.

---

## 12. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Renaming the package breaks an import path some doc/test still uses | Brand-residue gate + full `pytest` + `import omnidocbench_rocm` in CI matrix (3.10–3.12). |
| Someone cloned 0.1.0 and expects `omnidocbench-amd` | Never published, no pip consumers (audit evidence). CHANGELOG records the rename; no shim shipped by design. |
| Doc/reality drift re-introduced during rewrite | `architecture.md` rewrite is cross-checked against the actual `engine/omnidocbench_rocm/` tree; `ci-reality.md` already honest. |
| Makefile fix breaks existing per-model repos' muscle memory | Documented in CHANGELOG + template README; old two-target-on-one-recipe behavior was already buggy. |
| Over-deletion: removing a doc another live file links to | Commit 1 fixes inbound references; brand-residue + link-check CI catch dangling links. |
| Schema `$id` change invalidates cached validators | `$id` is non-resolving and unused for network fetch; local validators key off `$defs`. No impact. |
| Premature remote rename strands the PR | Rename is explicitly gated behind green CI + user go; never auto-run. |

---

## 13. Open questions

None. All decisions resolved in the brainstorming session:
- Scope: one spec → one plan → 6 commits.
- Legacy surface: dropped (no shim), per evidence + user directive to avoid user confusion.
- Historical stale docs: deleted (clean break).
- Execution: local implement → push branch → open PR; remote rename gated.

---

## Next step

Upon user approval of this written spec → invoke **writing-plans** to produce the step-by-step implementation plan (`docs/superpowers/plans/2026-07-19-omnidocbench-rocm-migration.md`), then execute the 6 commits.
