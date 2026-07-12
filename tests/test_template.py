"""Task 10: cookiecutter per-model template + smoke backend.

Renders the ``template/`` cookiecutter project into a tmp dir, then:

1. ``test_rendered_template_passes_conformance`` — runs the engine's
   ``check_repo`` over the rendered repo and asserts every conformance check
   passes (layout, README sections, engine dependency, schema-valid model_card).
2. ``test_rendered_template_smoke_backend_runs`` — runs the rendered
   ``run_adapter.py --backend smoke`` with no GPU and asserts it writes
   ``out_dir/<stem>.md`` per image + exits 0.

If both pass, a contributor copying this template starts from a conformant,
smoke-runnable repo.
"""
import subprocess, sys
from pathlib import Path
from cookiecutter.main import cookiecutter
from scripts.check_conformance import check_repo

TEMPLATE = Path(__file__).parent.parent / "template"


def test_rendered_template_passes_conformance(tmp_path):
    out = cookiecutter(str(TEMPLATE), no_input=True,
                       extra_context={"repo_name": "SmokeModel-AMD", "model_slug": "smokemodel"},
                       output_dir=str(tmp_path))
    report = check_repo(Path(out))
    assert report.ok, report.failures


def test_rendered_template_smoke_backend_runs(tmp_path):
    out = cookiecutter(str(TEMPLATE), no_input=True,
                       extra_context={"repo_name": "SmokeModel-AMD", "model_slug": "smokemodel"},
                       output_dir=str(tmp_path))
    adapter = Path(out) / "adapter" / "run_adapter.py"
    imgs = tmp_path / "imgs"; imgs.mkdir(); (imgs / "a.png").write_bytes(b"x")
    proc = subprocess.run([sys.executable, str(adapter), "--img-dir", str(imgs),
                           "--out-dir", str(tmp_path / "out"), "--platform", "linux-rocm",
                           "--backend", "smoke"])
    assert proc.returncode == 0
    assert (tmp_path / "out" / "a.md").exists()
