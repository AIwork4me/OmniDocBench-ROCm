#!/usr/bin/env bash
# Provision the Python 3.11 eval-venv at $OMNIDOCBENCH_ROCM_DATA/eval-venv/linux-rocm.
# OmniDocBench scoring breaks on 3.12 (inspect.getargspec/distutils/imp); 3.11 is required.
set -euo pipefail
DATA_ROOT="${OMNIDOCBENCH_ROCM_DATA:-/root/ocr-eval/omnidocbench-rocm-data}"
VENV="$DATA_ROOT/eval-venv/linux-rocm"
ODB="${OMNIDOCBENCH_CHECKOUT:-/workspace/OmniDocBench}"

if [ -x "$VENV/bin/python" ]; then
  echo "[eval-venv] already present at $VENV ($($VENV/bin/python --version))"
else
  echo "[eval-venv] creating 3.11 venv at $VENV"
  /usr/bin/python3.11 -m venv "$VENV"
fi
ver="$($VENV/bin/python --version 2>&1)"
case "$ver" in *3.11*) echo "[eval-venv] python: $ver";; *) echo "[eval-venv] FATAL: need 3.11, got $ver" >&2; exit 1;; esac

$VENV/bin/pip install -U pip -q
# OmniDocBench scorer (pinned checkout) + CDM smoke needs (Pillow).
if [ -f "$ODB/setup.py" ] || [ -f "$ODB/pyproject.toml" ]; then
  $VENV/bin/pip install -e "$ODB" -q
fi
$VENV/bin/pip install Pillow -q
echo "[eval-venv] ready: $VENV"
