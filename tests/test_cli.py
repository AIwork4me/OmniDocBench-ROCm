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
