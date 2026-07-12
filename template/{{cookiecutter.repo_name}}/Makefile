PLATFORM ?= linux-rocm
VERSION  ?= v16
REVISION ?= v1.6
MODEL_ID ?= {{cookiecutter.model_id}}

setup-linux:
	bash adapter/setup/00-install-deps.sh
setup-windows:
	powershell -ExecutionPolicy Bypass -File adapter\setup\00-install-deps.ps1

demo:
	OUT=$$(mktemp -d); omnidocbench-amd infer --adapter adapter/run_adapter.py --img-dir examples --out-dir $$OUT --platform $(PLATFORM); ls $$OUT

eval-linux eval-windows:
	omnidocbench-amd run --stage all --platform $(PLATFORM) --version $(VERSION) --revision $(REVISION)

publish:
	omnidocbench-amd conformance . && echo CONFORMANT

smoke-test:
	python -m pytest
