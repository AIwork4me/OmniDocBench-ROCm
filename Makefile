.PHONY: provision-cdm repro-score test setup-linux

setup-linux:
	bash engine/omnidocbench_rocm/evalenv/setup-linux.sh

provision-cdm:
	omnidocbench-rocm cdm setup --platform linux-rocm

repro-score:
	@echo "Build the image (Docker-capable box), then:"
	@echo "  docker run --rm -v $$PREDICTIONS:/preds -v $$GT/OmniDocBench.json:/gt/OmniDocBench.json \\"
	@echo "    omnidocbench-rocm-repro:0.2.0 score --platform linux-rocm --predictions-dir /preds --version v16 --run-stats /preds/_run_stats.json --dataset-dir /gt"
	@echo "Then: python scripts/check_verified.py VERIFIED.yaml"

test:
	python -m pytest -q
