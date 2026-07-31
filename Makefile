.PHONY: provision-cdm repro-score test setup-linux hub-regen ci

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

hub-regen:
	@echo "Rebuilding canonical (imports+legacy) + README (results section + comparison table)..."
	python scripts/regen_hub.py

ci: ## run the full local CI gate set (quality + contracts) BEFORE push
	@echo "==> validate_registry"; python scripts/validate_registry.py hub/registry.yaml
	@echo "==> canonical/results-section freshness"; python -m omnidocbench_rocm.registry generate --check
	@echo "==> comparison-table freshness"; python scripts/generate_registry.py hub/registry.yaml --check
	@echo "==> check_brand"; python scripts/check_brand.py
	@echo "==> check_license_class"; python scripts/check_license_class.py
	@echo "==> check_result_ids"; python scripts/check_result_ids.py
	@echo "==> build"; python -m build
	@echo "==> pytest"; python -m pytest -q
	@echo "ci: all gates green ✓"
