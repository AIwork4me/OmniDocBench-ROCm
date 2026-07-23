import yaml
from pathlib import Path
from omnidocbench_rocm.config_render import render_config

TEMPLATE = Path(__file__).resolve().parent.parent / "engine" / "omnidocbench_rocm" / "data" / "omnidocbench_v16.yaml.tmpl"


def _load(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))


def test_render_paths_nocdm(tmp_path):
    prediction_path = Path("/preds/x")
    gt_path = Path("/data/OmniDocBench.json")
    out = render_config(TEMPLATE, prediction_path=prediction_path,
                        gt_path=gt_path, cdm=False)
    cfg = _load(out)["end2end_eval"]
    assert cfg["dataset"]["prediction"]["data_path"] == str(prediction_path)
    assert cfg["dataset"]["ground_truth"]["data_path"] == str(gt_path)
    assert cfg["metrics"]["display_formula"]["metric"] == ["Edit_dist"]


def test_render_cdm_variant(tmp_path):
    out = render_config(TEMPLATE, prediction_path=Path("/preds/x_cdm"),
                        gt_path=Path("/data/OmniDocBench.json"), cdm=True)
    df = _load(out)["end2end_eval"]["metrics"]["display_formula"]
    assert df["metric"] == ["Edit_dist", "CDM"]
    assert df["cdm_workers"] == 13
