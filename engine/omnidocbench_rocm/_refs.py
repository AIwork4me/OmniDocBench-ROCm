"""Pinned upstream refs so dataset and scorer stay aligned and reproducible."""
from __future__ import annotations

# OmniDocBench checkout commit matching the v1.6 dataset. Must align with the
# revision stage_download pins. Bump only with a coordinated dataset bump.
OMNIDOCBENCH_V16_REF = "2b161d0"
