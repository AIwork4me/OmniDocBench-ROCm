#!/usr/bin/env bash
# Provision the Python 3.11 eval-venv at $OMNIDOCBENCH_ROCM_DATA/eval-venv/linux-rocm.
# OmniDocBench scoring breaks on 3.12 (inspect.getargspec/distutils/imp); 3.11 is required.
#
# IMPORTANT: CDM scoring uses multiprocessing.Pool(200). A separately-created venv
# may have subtle multiprocessing differences that break CDM workers ("can only
# join a started process"). The OmniDocBench checkout's own .venv (created by
# OmniDocBench's setup) is the KNOWN-WORKING scorer venv. We prefer it.
set -euo pipefail
DATA_ROOT="${OMNIDOCBENCH_ROCM_DATA:-/root/ocr-eval/omnidocbench-rocm-data}"
VENV="$DATA_ROOT/eval-venv/linux-rocm"
ODB="${OMNIDOCBENCH_CHECKOUT:-/workspace/OmniDocBench}"

# Prefer the OmniDocBench checkout's own .venv (known-working for CDM).
if [ -x "$ODB/.venv/bin/python" ]; then
  echo "[eval-venv] using OmniDocBench checkout's .venv (known-working for CDM)"
  ln -sfn "$ODB/.venv" "$VENV"
elif [ -x "$VENV/bin/python" ]; then
  echo "[eval-venv] already present at $VENV ($($VENV/bin/python --version))"
else
  echo "[eval-venv] WARNING: creating a new 3.11 venv — CDM Pool(200) may fail;"
  echo "[eval-venv]   prefer running OmniDocBench's own setup to create .venv first."
  /usr/bin/python3.11 -m venv "$VENV"
fi

ver="$($VENV/bin/python --version 2>&1)"
case "$ver" in *3.11*) echo "[eval-venv] python: $ver";; *) echo "[eval-venv] FATAL: need 3.11, got $ver" >&2; exit 1;; esac

# If using a fresh venv (not the checkout's .venv), install OmniDocBench + Pillow.
if [ ! -x "$ODB/.venv/bin/python" ]; then
  $VENV/bin/pip install -U pip -q
  if [ -f "$ODB/setup.py" ] || [ -f "$ODB/pyproject.toml" ]; then
    $VENV/bin/pip install -e "$ODB" -q
  fi
  $VENV/bin/pip install Pillow -q
fi
echo "[eval-venv] ready: $VENV -> $(readlink -f "$VENV")"
