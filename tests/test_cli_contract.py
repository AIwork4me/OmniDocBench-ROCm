"""Tests for the standard CLI contract data + output validators (ADR-0011)."""
import pytest
from omnidocbench_rocm import cli_contract as cc


def test_exit_codes_normative():
    assert cc.EXIT_CODES == {"OK": 0, "PARTIAL": 1, "USAGE": 2,
                             "BACKEND_MISMATCH": 3, "CONTRACT": 4, "FATAL": 5}
    assert cc.STANDARD_COMMANDS == ("version", "capabilities", "doctor", "parse")


def test_standard_doc_exit_codes_match_implementation():
    """ROCMDOC_STANDARD.md §3.1 exit-code table must match cli_contract.EXIT_CODES.

    Round-2 P1-1: the umbrella normative doc had drifted from the implemented+
    locked contract (it read 3=env-ready/4=backend-mismatch vs the real
    3=BACKEND_MISMATCH/4=CONTRACT). This guard asserts the doc carries every
    implemented code<->name pair so the drift cannot recur silently. The locked
    contract of record is cli_contract.EXIT_CODES (mirrored in cli-contract.md §2
    and each model repo's spec-lock cli_exit_codes).
    """
    from pathlib import Path
    standard = Path(__file__).resolve().parents[1] / "contracts" / "ROCMDOC_STANDARD.md"
    text = standard.read_text(encoding="utf-8")
    for name, code in cc.EXIT_CODES.items():
        assert f"| {code} | {name} |" in text, (
            f"ROCMDOC_STANDARD.md §3.1 missing/mismatched exit-code row for code {code} "
            f"(expected name {name}); umbrella doc must match cli_contract.EXIT_CODES "
            "(see cli-contract.md §2)"
        )


def test_parse_json_stdout_pure_and_impure():
    clean = cc.CLIRun(stdout='{"name": "x", "version": "1"}', stderr="", returncode=0)
    obj, err = cc.parse_json_stdout(clean)
    assert err is None and obj["name"] == "x"

    noisy = cc.CLIRun(stdout='[boot]\n{"name": "x"}\n[done]', stderr="", returncode=0)
    obj, err = cc.parse_json_stdout(noisy)
    assert obj is None and err is not None  # CONTRACT violation: not pure JSON

    empty = cc.CLIRun(stdout="", stderr="", returncode=0)
    assert cc.parse_json_stdout(empty)[1] is not None


def test_validate_outputs():
    assert cc.validate_version_output({"name": "x", "version": "1"}) == []
    assert cc.validate_version_output({"name": "x"})  # missing version
    assert cc.validate_capabilities_output({"platforms": [{"platform": "linux-rocm", "backend": "vllm"}]}) == []
    assert cc.validate_capabilities_output({})  # missing platforms
    assert cc.validate_result_output({"schema_version": 1, "status": "ok", "pages": []}) == []
    assert cc.validate_doctor_output({"status": "ready"}) == []
    assert cc.validate_doctor_output({"status": "maybe"})  # bad status
    assert cc.validate_doctor_output({})  # missing status


def test_check_backend_match():
    res = {"backend": "onnx-rocm"}
    assert cc.check_backend_match(res, "") is None          # no request -> skip
    assert cc.check_backend_match(res, "onnx-rocm") is None  # match
    bad = cc.check_backend_match(res, "vllm")
    assert bad is not None and "mismatch" in bad
