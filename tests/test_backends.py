from pathlib import Path
from unittest.mock import patch
from omnidocbench_amd.backends.linux_rocm import LinuxRocmBackend


def test_score_invokes_pdf_validation_in_eval_venv(tmp_path):
    backend = LinuxRocmBackend(checkout=tmp_path / "odb")
    (tmp_path / "odb").mkdir()
    (tmp_path / "odb" / "pdf_validation.py").write_text("# stub")
    metric_path = tmp_path / "result" / "preds_quick_match_metric_result.json"
    metric_path.parent.mkdir(parents=True)
    metric_path.write_text("{}")
    with patch("omnidocbench_amd.backends.linux_rocm.subprocess.run") as run:
        run.return_value.returncode = 0
        out = backend.score(predictions_dir=tmp_path / "preds", version="v16",
                            cdm=False, run_stats_path=tmp_path / "rs.json")
    assert out.name == "preds_quick_match_metric_result.json"
    assert run.call_args.args[0][1].endswith("pdf_validation.py")  # runs the checkout's script
