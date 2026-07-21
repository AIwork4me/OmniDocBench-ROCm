PLATFORM ?= linux-rocm
VERSION  ?= v16
REVISION ?= v1.6
MODEL_ID ?= {{cookiecutter.model_id}}
# Optional backend/server config forwarded to the adapter (empty = use adapter_config.py defaults).
BACKEND       ?=
SERVER_URL    ?=
API_MODEL_NAME ?=

setup-linux:
	bash adapter/setup/00-install-deps.sh
setup-windows:
	powershell -ExecutionPolicy Bypass -File adapter\setup\00-install-deps.ps1

demo:
	OUT=$$(mktemp -d); omnidocbench-rocm infer --adapter adapter/run_adapter.py --img-dir examples --out-dir $$OUT --platform $(PLATFORM); ls $$OUT

eval-linux:
	omnidocbench-rocm run --stage all --platform linux-rocm --version $(VERSION) --revision $(REVISION) \
	  --adapter adapter/run_adapter.py --model-id $(MODEL_ID) \
	  $(if $(BACKEND),--backend $(BACKEND)) \
	  $(if $(SERVER_URL),--server-url $(SERVER_URL)) \
	  $(if $(API_MODEL_NAME),--api-model-name $(API_MODEL_NAME)) \
	  --git-commit $$(git rev-parse HEAD) --results-dir results/omnidocbench/$(VERSION)/linux-rocm

eval-windows:
	omnidocbench-rocm run --stage all --platform windows-hip --version $(VERSION) --revision $(REVISION) \
	  --adapter adapter/run_adapter.py --model-id $(MODEL_ID) \
	  $(if $(BACKEND),--backend $(BACKEND)) \
	  $(if $(SERVER_URL),--server-url $(SERVER_URL)) \
	  $(if $(API_MODEL_NAME),--api-model-name $(API_MODEL_NAME)) \
	  --git-commit $$(git rev-parse HEAD) --results-dir results/omnidocbench/$(VERSION)/windows-hip

publish:
	omnidocbench-rocm conformance . && echo CONFORMANT

smoke-test:
	python -m pytest
