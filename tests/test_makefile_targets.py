"""Assert the template Makefile's eval-linux/eval-windows targets pass the
correct --platform (spec §VIII: the old shared-PLATFORM-default bug, where
`make eval-windows` silently ran Linux, must stay fixed). Parses recipe text
rather than invoking make (no render needed)."""
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parent.parent / "template" / "{{cookiecutter.repo_name}}" / "Makefile"


def _recipe(target: str) -> str:
    text = MAKEFILE.read_text()
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(f"{target}:"))
    body = []
    for l in lines[start + 1:]:
        if l and not l.startswith("\t") and not l.startswith(" "):
            break
        body.append(l)
    return "\n".join(body)


def test_targets_are_separate_recipes():
    text = MAKEFILE.read_text()
    assert "eval-linux eval-windows:" not in text
    assert text.count("eval-linux:") == 1
    assert text.count("eval-windows:") == 1


def test_eval_linux_uses_linux_rocm():
    r = _recipe("eval-linux")
    assert "--platform linux-rocm" in r
    assert r.rstrip().endswith("linux-rocm")


def test_eval_windows_uses_windows_hip():
    r = _recipe("eval-windows")
    assert "--platform windows-hip" in r
    assert r.rstrip().endswith("windows-hip")
