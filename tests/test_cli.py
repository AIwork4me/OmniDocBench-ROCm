import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from omnidocbench_amd.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_cli_score_dispatches_to_stage_score(tmp_path):
    argv = ["omnidocbench-amd", "score", "--platform", "linux-rocm",
            "--predictions-dir", str(tmp_path), "--version", "v16",
            "--run-stats", str(tmp_path / "rs.json")]
    with patch("omnidocbench_amd.cli.stage_score") as score, \
         patch("omnidocbench_amd.cli.get_backend") as gb:
        gb.return_value.score.return_value = tmp_path / "metric.json"
        main(argv[1:])
        assert score.called or gb.return_value.score.called


def test_cli_cdm_setup_dispatches():
    with patch("omnidocbench_amd.cli.get_backend") as gb:
        main(["cdm", "setup", "--platform", "linux-rocm"])
        gb.return_value.provision_cdm.assert_called_once()


def test_cli_conformance_conformant_repo_exits_zero(capsys):
    rc = main(["conformance", str(FIX / "conformant")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "CONFORMANT" in out


def test_cli_conformance_nonconformant_repo_exits_one(capsys):
    rc = main(["conformance", str(FIX / "nonconformant")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "NON-CONFORMANT" in out


def test_cli_run_all_orchestrates_four_stages_in_order(tmp_path):
    """`run --stage all` calls download -> infer -> score -> publish in order."""
    call_order: list[str] = []

    with patch("omnidocbench_amd.cli.stage_download") as dl, \
         patch("omnidocbench_amd.cli.stage_infer") as inf, \
         patch("omnidocbench_amd.cli.stage_score") as sc, \
         patch("omnidocbench_amd.cli.stage_publish") as pub, \
         patch("omnidocbench_amd.cli.get_backend") as gb:
        # Each side_effect records its stage name into the shared list.
        dl.side_effect = lambda version, revision: (
            call_order.append("download") or tmp_path / "dataset")
        inf.side_effect = lambda **kw: (
            call_order.append("infer") or {"count": 0, "ok": 0})
        sc.side_effect = lambda **kw: (
            call_order.append("score") or tmp_path / "metric.json")
        pub.side_effect = lambda **kw: (
            call_order.append("publish") or {"run_summary": "x", "provenance": "y"})
        gb.return_value.score.return_value = tmp_path / "metric.json"

        rc = main([
            "run", "--stage", "all",
            "--platform", "linux-rocm",
            "--version", "v16",
            "--revision", "v1.6",
            "--adapter", "fake.py",
            "--model-id", "m",
            "--git-commit", "abc123",
            "--results-dir", str(tmp_path),
        ])

    assert rc == 0
    # Assert ORDER, not just that each was called.
    assert call_order == ["download", "infer", "score", "publish"]
    # All four stages invoked exactly once.
    assert dl.call_count == 1
    assert inf.call_count == 1
    assert sc.call_count == 1
    assert pub.call_count == 1
    # download receives version + revision.
    dl.assert_called_once_with("v16", "v1.6")
