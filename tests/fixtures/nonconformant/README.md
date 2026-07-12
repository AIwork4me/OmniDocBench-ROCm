# fixture-model (NON-conformant)

A deliberately non-conformant fixture repo. It is missing `adapter/run_adapter.py`
and `README.zh-CN.md`, and declares an empty `results/` directory, so
`check_conformance` must report failures.

## Install

```bash
pip install -e .
```

## Demo

No runnable demo — adapter is missing.

## Evaluation

Config present at `eval/configs/omnidocbench_v16.yaml`, but no adapter to run.

## Reproducibility

Not reproducible: no adapter, no committed results artifacts.

## Known Gaps

- Missing `adapter/run_adapter.py`.
- Missing `README.zh-CN.md`.
- Empty `results/omnidocbench/v16/linux-rocm/`.
