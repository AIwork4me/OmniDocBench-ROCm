from pathlib import Path
from unittest.mock import patch
import pytest
from omnidocbench_rocm.backends import get_backend
from omnidocbench_rocm.backends.linux_rocm import LinuxRocmBackend


def _stub_checkout(tmp_path):
    """Create a stub OmniDocBench checkout with pdf_validation.py and an eval-venv."""
    (tmp_path / "odb").mkdir()
    (tmp_path / "odb" / "pdf_validation.py").write_text("# stub")
    (tmp_path / "venv" / "bin").mkdir(parents=True)
    (tmp_path / "venv" / "bin" / "python").write_text("#!/bin/sh\n")


def _stub_dataset(tmp_path, name="ds"):
    ds_dir = tmp_path / name
    ds_dir.mkdir()
    (ds_dir / "OmniDocBench.json").write_text("{}")
    return ds_dir


def test_score_invokes_pdf_validation_in_eval_venv(tmp_path):
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    _stub_checkout(tmp_path)
    metric_path = tmp_path / "result" / "preds_quick_match_metric_result.json"
    metric_path.parent.mkdir(parents=True)
    metric_path.write_text("{}")
    ds_dir = _stub_dataset(tmp_path)
    with patch("omnidocbench_rocm.backends.linux_rocm.subprocess.run") as run, \
         patch("omnidocbench_rocm.backends.linux_rocm.eval_venv") as ev:
        ev.return_value = tmp_path / "venv"
        run.return_value.returncode = 0
        out = backend.score(predictions_dir=tmp_path / "preds", version="v16",
                            cdm=False, run_stats_path=tmp_path / "rs.json",
                            dataset_dir=ds_dir)
    assert out.name == "preds_quick_match_metric_result.json"
    assert run.call_args.args[0][1].endswith("pdf_validation.py")  # runs the checkout's script


def test_score_invokes_pdf_validation_with_config_only(tmp_path):
    """score() renders a config and calls pdf_validation --config <path> (no --predictions)."""
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    _stub_checkout(tmp_path)
    preds = tmp_path / "preds"; preds.mkdir()
    ds_dir = _stub_dataset(tmp_path)
    with patch("omnidocbench_rocm.backends.linux_rocm.subprocess.run") as run, \
         patch("omnidocbench_rocm.backends.linux_rocm.eval_venv") as ev:
        ev.return_value = tmp_path / "venv"
        backend.score(predictions_dir=preds, version="v16", cdm=False,
                      run_stats_path=tmp_path / "rs.json", dataset_dir=ds_dir)
    cmd = run.call_args.args[0]
    assert cmd[1].endswith("pdf_validation.py")
    assert cmd[2] == "--config"
    assert "--predictions" not in cmd


def test_score_cdm_variant_rendered(tmp_path):
    from omnidocbench_rocm.backends.linux_rocm import LinuxRocmBackend
    import yaml
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    _stub_checkout(tmp_path)
    (tmp_path / "result").mkdir()
    preds = tmp_path / "preds_cdm"; preds.mkdir()
    ds_dir = _stub_dataset(tmp_path)
    captured = {}
    def fake_run(cmd, **kw):
        captured["config"] = cmd[3]
        (tmp_path / "result" / "preds_cdm_quick_match_metric_result.json").write_text("{}")
        class R: returncode = 0
        return R()
    with patch("omnidocbench_rocm.backends.linux_rocm.subprocess.run", side_effect=fake_run), \
         patch("omnidocbench_rocm.backends.linux_rocm.eval_venv") as ev:
        ev.return_value = tmp_path / "venv"
        backend.score(predictions_dir=preds, version="v16", cdm=True,
                      run_stats_path=tmp_path / "rs.json", dataset_dir=ds_dir)
    cfg = yaml.safe_load(open(captured["config"]))["end2end_eval"]["metrics"]["display_formula"]
    assert "CDM" in cfg["metric"]


def test_windows_hip_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="windows-hip"):
        get_backend("windows-hip")


def test_linux_rocm_backend_resolves():
    b = get_backend("linux-rocm")
    assert b.__class__.__name__ == "LinuxRocmBackend"


def test_unknown_platform_raises_value_error():
    with pytest.raises(ValueError):
        get_backend("does-not-exist")
