# Conformance Checklist

A per-model repository is **conformant** when it passes
`python scripts/check_conformance.py <repo>` (exit 0). The script is the single
source of truth for this checklist; this document mirrors it exactly. Run it in
CI on every model repo and before awarding any badge.

## What `check_repo` enforces

| # | Check | Failure message |
|---|-------|-----------------|
| 1 | `adapter/run_adapter.py` exists | `missing adapter/run_adapter.py` |
| 2 | `eval/configs/omnidocbench_v16.yaml` exists | `missing eval/configs/omnidocbench_v16.yaml` |
| 3 | Each declared `results/omnidocbench/v16/<platform>/` dir holds a real artifact (checked for `linux-rocm` and `windows-hip`; git placeholders like `.gitkeep` don't count) | `empty results/omnidocbench/v16/<plat>/ (declared but no artifacts)` |
| 4 | Both `README.md` and `README.zh-CN.md` exist | `missing <readme>` |
| 5 | Each README contains the required section headers: **Install**, **Demo**, **Evaluation**, **Reproducibility**, **Known Gaps** | `<readme> missing required section: <sec>` |
| 6 | `examples/` is a non-empty directory | `missing examples/ demo` |
| 7 | `pyproject.toml` exists and depends on `omnidocbench-amd` | `pyproject.toml does not depend on omnidocbench-amd` |
| 8 | If `model_card.json` exists, it validates against the `model_card` `$def` of `contracts/artifact-schema.json` | `model_card.json invalid: <error>` |

## Required README sections

Every model repo must ship bilingual READMEs (`README.md` in English,
`README.zh-CN.md` in Simplified Chinese). Both must contain these section
headers (the checker matches the bare word, so `## Install` / `## 安装 (Install)`
/ `### Installation (Install)` all satisfy it):

- **Install** — how to install the model + engine.
- **Demo** — a one-command smoke demo (`examples/run_demo.sh`).
- **Evaluation** — the `omnidocbench-amd` command(s) to reproduce results.
- **Reproducibility** — hardware, driver, commit, and artifact locations.
- **Known Gaps** — known limitations, missing platforms, fallbacks.

## Required layout

```
<model-repo>/
  adapter/run_adapter.py            # canonical adapter entrypoint
  eval/configs/omnidocbench_v16.yaml
  results/omnidocbench/v16/<platform>/   # non-empty when declared
  examples/                          # non-empty (demo.png + run_demo.sh)
  README.md
  README.zh-CN.md
  pyproject.toml                     # depends on omnidocbench-amd
  model_card.json                    # schema-valid (optional but recommended)
```

## Running

```bash
# From the OmniDocBench-AMD repo (or any checkout with scripts/):
python scripts/check_conformance.py path/to/model-repo
# -> CONFORMANT (exit 0) | NON-CONFORMANT + failure list (exit 1)
```

In Python:

```python
from scripts.check_conformance import check_repo
report = check_repo(Path("path/to/model-repo"))
print(report.ok, report.failures)
```

See `contracts/badge-policy.md` for how conformance maps to badge tiers.
