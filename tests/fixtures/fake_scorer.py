#!/usr/bin/env python3
"""Tiny fixture scorer for the score-reproduction conformance profile (CI only).

Prints fixed metrics as JSON on stdout. This is NOT a real scorer — it exists so
the score-reproduction profile can be EXERCISED in GPU-less CI. Per Round-2 §4.3,
a pass against this fixture does NOT promote any result's platform_review: the
profile only proves the replay *mechanism* works, not that a real score was
reproduced. That requires the real OmniDocBench scorer on real predictions.
"""
import argparse
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--predictions-dir", default="")
    ap.add_argument("--overall", type=float, default=95.0)
    ap.add_argument("--fail", action="store_true", help="exit nonzero to simulate scorer failure")
    args = ap.parse_args()
    if args.fail:
        print("simulated scorer failure", file=sys.stderr)
        return 2
    # honor the offline/deny convention: this fixture never touches the network,
    # but a conformant real scorer must also respect ROCMDOC_NETWORK_DENY.
    metrics = {"overall": args.overall, "edit_dist": 1.0, "table_teds_percent": 94.0}
    json.dump(metrics, sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
