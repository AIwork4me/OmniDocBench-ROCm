---
model_id: "{{ cookiecutter.model_id }}"
backend: "{{ cookiecutter.backend }}"
hardware:
  gpu: "{{ cookiecutter.gpu }}"
environment:
  type: "{{ cookiecutter.env_type }}"
command: |
  # TODO: fill in your reproduction command
expected_overall:
  value: 0.0
---

# Reproduce {{ cookiecutter.model_id }} on AMD ROCm

## Prerequisites

1. `rocminfo` outputs GPU info: `rocminfo | grep -E "Name:|VRAM"`
2. `/dev/kfd` accessible: `ls -la /dev/kfd`
3. VRAM >= minimum required (see environment)

## Quickstart

TODO: fill in the paste-and-run command for your model.

```bash
# TODO: docker run or venv command
```

## Expected output

Overall **TODO** (+/-0.5 tolerance). Full run takes ~TODO.

## If it fails

See [OmniDocBench-ROCm pitfalls](https://github.com/AIwork4me/OmniDocBench-ROCm/docs/pitfalls.md).
