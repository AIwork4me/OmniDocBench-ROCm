import sys
from unittest.mock import patch
from omnidocbench_amd.cli import main


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
