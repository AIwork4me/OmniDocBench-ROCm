from pathlib import Path
from unittest.mock import patch
from omnidocbench_rocm import download_omnidocbench as dl


def test_download_requires_pinned_revision(tmp_path):
    try:
        dl.download_dataset("opendatalab/OmniDocBench", tmp_path, revision=None)
        assert False
    except SystemExit:
        pass


def test_download_calls_snapshot_with_revision(tmp_path):
    with patch("omnidocbench_rocm.download_omnidocbench.snapshot_download") as snap:
        snap.return_value = str(tmp_path)
        out = dl.download_dataset("opendatalab/OmniDocBench", tmp_path, revision="v1.6")
        assert out == tmp_path
        assert snap.call_args.kwargs["revision"] == "v1.6"
