"""Standard CLI contract for per-model adapters (ADR-0011).

The central repo DEFINES this contract and VALIDATES adapters against it; it
never implements a model runtime and never imports torch/vllm/paddle (the
adapter runs as a subprocess — R1 of the adapter contract is preserved). The
contract is four JSON-emitting subcommands plus a fixed exit-code scheme:

    <cli> version        --json     # identity
    <cli> capabilities   --json     # declared platforms/backends/interfaces
    <cli> doctor         --json     # readiness / offline check
    <cli> parse <args>   --json     # parse pages -> canonical result.json

Exit codes (normative):

    0  OK                 full success
    1  PARTIAL            run completed, some pages failed (never raised per-page)
    2  USAGE              argument / misuse error
    3  BACKEND_MISMATCH   requested backend != the one that actually ran
    4  CONTRACT           stdout was not valid JSON or missed required fields
    5  FATAL              uncaught crash / no output produced

The canonical ``parse`` output is the ``cli_result`` $def. This module holds the
contract DATA + output validators; :mod:`conformance_profiles` runs the CLIs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .schema import iter_validation_errors

# Exit codes (see module docstring).
EXIT_OK = 0
EXIT_PARTIAL = 1
EXIT_USAGE = 2
EXIT_BACKEND_MISMATCH = 3
EXIT_CONTRACT = 4
EXIT_FATAL = 5

EXIT_CODES = {
    "OK": EXIT_OK,
    "PARTIAL": EXIT_PARTIAL,
    "USAGE": EXIT_USAGE,
    "BACKEND_MISMATCH": EXIT_BACKEND_MISMATCH,
    "CONTRACT": EXIT_CONTRACT,
    "FATAL": EXIT_FATAL,
}

# The four standard subcommands every conformant CLI must implement.
STANDARD_COMMANDS = ("version", "capabilities", "doctor", "parse")


@dataclass
class CLIRun:
    """Result of one CLI subprocess invocation."""
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == EXIT_OK


def parse_json_stdout(run: CLIRun) -> tuple[dict | None, str | None]:
    """Parse a CLI run's stdout as PURE JSON.

    Returns ``(obj, error)``. ``error`` is set when stdout is empty, not valid
    JSON, or has non-JSON noise around it (logs mixed in) — the CONTRACT
    violation (exit 4) case. A clean CLI prints exactly one JSON document.
    """
    raw = (run.stdout or "").strip()
    if not raw:
        return None, "empty stdout (expected a JSON document)"
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, f"stdout is not valid JSON: {e}"
    if not isinstance(obj, dict):
        return None, "stdout JSON is not an object"
    return obj, None


def validate_version_output(obj: dict) -> list[str]:
    return [f"version: {m}" for m in iter_validation_errors("cli_version", obj)]


def validate_capabilities_output(obj: dict) -> list[str]:
    return [f"capabilities: {m}" for m in iter_validation_errors("cli_capabilities", obj)]


def validate_result_output(obj: dict) -> list[str]:
    return [f"result: {m}" for m in iter_validation_errors("cli_result", obj)]


def validate_doctor_output(obj: dict) -> list[str]:
    """doctor --json is loosely specified: it must be a JSON object reporting
    readiness. We require a ``status`` field so the contract is testable without
    over-constraining the diagnostics payload."""
    if not isinstance(obj, dict):
        return ["doctor: output is not a JSON object"]
    problems: list[str] = []
    if "status" not in obj:
        problems.append("doctor: missing required 'status' field")
    if "status" in obj and obj["status"] not in ("ready", "not-ready"):
        problems.append(f"doctor: status must be 'ready' or 'not-ready', got {obj['status']!r}")
    return problems


def check_backend_match(result_obj: dict, requested_backend: str) -> str | None:
    """Return an error string if the result's actual backend != requested.

    The adapter is the only component that knows which inference path actually
    executed (R-bridge of the adapter contract). A mismatch is a BACKEND_MISMATCH
    (exit 3), never silently recorded. Empty ``requested_backend`` skips the
    check (adapter default accepted).
    """
    if not requested_backend:
        return None
    actual = result_obj.get("backend") or result_obj.get("engine")
    if actual and actual != requested_backend:
        return (f"backend mismatch: requested {requested_backend!r} but result reports "
                f"{actual!r} (exit {EXIT_BACKEND_MISMATCH})")
    return None
