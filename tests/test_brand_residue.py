from pathlib import Path
from scripts.check_brand import find_residue

ROOT = Path(__file__).resolve().parent.parent


def test_repo_is_brand_clean():
    hits = find_residue(ROOT)
    assert hits == [], hits


def test_exclusions_and_detection(tmp_path):
    (tmp_path / "README.md").write_text("bad: omnidocbench-amd\n")
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "x.py").write_text("# omnidocbench_amd\n")
    (tmp_path / "docs" / "superpowers").mkdir(parents=True)
    (tmp_path / "docs" / "superpowers" / "s.md").write_text("ok: omnidocbench-amd\n")
    (tmp_path / "docs" / "audits").mkdir(parents=True)
    (tmp_path / "docs" / "audits" / "a.md").write_text("ok: OmniDocBench-AMD\n")
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0001.md").write_text("ok: omnidocbench-amd\n")
    (tmp_path / "CHANGELOG.md").write_text("ok: omnidocbench-amd\n")
    hits = find_residue(tmp_path)
    rels = sorted(h[0] for h in hits)
    assert rels == ["README.md", "engine/x.py"]
