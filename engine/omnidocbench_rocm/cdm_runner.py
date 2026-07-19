"""Host CDM provisioning runner (Linux). Invoked by LinuxRocmBackend.provision_cdm."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

CDM_DIR = Path(__file__).resolve().parent / "cdm"


def provision_cdm_linux() -> None:
    setup = CDM_DIR / "setup-linux.sh"
    smoke = CDM_DIR / "smoke_cdm.sh"
    print("[cdm] provisioning host CDM toolchain (setup-linux.sh)...")
    subprocess.run(["bash", str(setup)], check=True)
    print("[cdm] running smoke probe (smoke_cdm.sh)...")
    rc = subprocess.run(["bash", str(smoke)]).returncode
    if rc != 0:
        print("[cdm] WARNING: smoke probe failed — CDM scoring will likely yield "
              "all-exception (pending/null). Fix the reported failure mode before "
              "a real --cdm run. See docs/pitfalls.md (#cdm-zero).", file=sys.stderr)
