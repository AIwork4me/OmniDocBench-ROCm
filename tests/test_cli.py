import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from omnidocbench_rocm.cli import main
from omnidocbench_rocm.types import InferResult

FIX = Path(__file__).parent / "fixtures"


def test_cli_score_dispatches_to_stage_score(tmp_path):
    argv = ["omnidocbench-rocm", "score", "--platform", "linux-rocm",
            "--predictions-dir", str(tmp_path), "--version", "v16",
            "--run-stats", str(tmp_path / "rs.json")]
    with patch("omnidocbench_rocm.cli.stage_score") as score, \
         patch("omnidocbench_rocm.cli.get_backend") as gb:
        gb.return_value.score.return_value = tmp_path / "metric.json"
        main(argv[1:])
        assert score.called or gb.return_value.score.called


def test_cli_cdm_setup_dispatches():
    with patch("omnidocbench_rocm.cli.get_backend") as gb:
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

    with patch("omnidocbench_rocm.cli.stage_download") as dl, \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend") as gb:
        # Each side_effect records its stage name into the shared list.
        dl.side_effect = lambda version, revision: (
            call_order.append("download") or tmp_path / "dataset")
        inf.side_effect = lambda **kw: (
            call_order.append("infer")
            or InferResult(run_stats={"count": 0, "ok": 0},
                           adapter_argv=[sys.executable, "fake.py", "--backend", "x"]))
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


def test_cli_infer_forwards_config(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_infer") as inf:
        rc = main(["infer", "--adapter", "a.py", "--img-dir", "i", "--out-dir", "o",
                   "--platform", "linux-rocm", "--backend", "vlm-vllm",
                   "--server-url", "http://x/v1", "--api-model-name", "m", "--skip-existing"])
        assert rc == 0
        cfg = inf.call_args.kwargs["config"]
        assert cfg["backend"] == "vlm-vllm"
        assert cfg["server_url"] == "http://x/v1"
        assert cfg["api_model_name"] == "m"
        assert cfg["skip_existing"] is True


def test_cli_publish_requires_predictions_dir():
    with pytest.raises(SystemExit) as exc:
        main(["publish", "--model-id", "m", "--platform", "linux-rocm",
              "--run-stats", "r.json", "--metric-result", "m.json",
              "--results-dir", "r", "--git-commit", "c",
              "--adapter-command", "x", "--dataset-revision", "v1.6"])
    assert exc.value.code == 2   # argparse missing-required-arg


def test_run_all_uses_same_backend_for_infer_and_publish(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path),
                   "--backend", "vlm-vllm"])
        assert rc == 0
        assert inf.call_args.kwargs["config"]["backend"] == "vlm-vllm"
        assert pub.call_args.kwargs["requested_backend"] == "vlm-vllm"


def test_run_all_forwards_server_url_and_api_model_name(tmp_path):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path),
                   "--server-url", "http://x/v1", "--api-model-name", "m"])
        assert rc == 0
        cfg = inf.call_args.kwargs["config"]
        assert cfg["server_url"] == "http://x/v1" and cfg["api_model_name"] == "m"
        kw = pub.call_args.kwargs
        assert kw["server_url"] == "http://x/v1" and kw["api_model_name"] == "m"


def test_run_all_passes_out_dir_to_publish(tmp_path):
    from omnidocbench_rocm._paths import predictions_dir
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish") as pub, \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path)])
        assert rc == 0
        assert pub.call_args.kwargs["predictions_dir"] == predictions_dir("m", "linux-rocm")


def test_run_all_adapter_command_override_note(tmp_path, capsys):
    with patch("omnidocbench_rocm.cli.stage_download"), \
         patch("omnidocbench_rocm.cli.stage_infer") as inf, \
         patch("omnidocbench_rocm.cli.stage_score") as sc, \
         patch("omnidocbench_rocm.cli.stage_publish"), \
         patch("omnidocbench_rocm.cli.get_backend"):
        inf.return_value = InferResult(run_stats={"count": 0, "ok": 0},
                                       adapter_argv=[sys.executable, "fake.py"])
        sc.return_value = tmp_path / "metric.json"
        rc = main(["run", "--stage", "all", "--platform", "linux-rocm",
                   "--version", "v16", "--revision", "2b161d0", "--adapter", "fake.py",
                   "--model-id", "m", "--git-commit", "c", "--results-dir", str(tmp_path),
                   "--adapter-command", "user-supplied-cmd"])
        assert rc == 0
        err = capsys.readouterr().err.lower()
        assert "overriding" in err or "user-supplied" in err
