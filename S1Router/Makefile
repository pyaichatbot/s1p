PY := .venv/bin/python
NODE := node
export PYTHONPATH := $(CURDIR)/packages/contracts/src:$(CURDIR)/packages/router/src:$(CURDIR)/packages/model/src
export UV_CACHE_DIR := $(CURDIR)/.cache/uv
export PYTHONDONTWRITEBYTECODE := 1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD := 1
PYTEST := $(PY) -m pytest -p pytest_cov -p pytest_socket

.PHONY: bootstrap check lint types test ci audit release hooks kanban-check architecture layer deploy-local rollback-local local-status local-smoke

bootstrap:
	uv sync --locked --python 3.12.9

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check .

types:
	$(PY) -m mypy scripts tests packages

test:
	$(PYTEST) tests/tooling --cov=scripts --cov-branch --cov-report=term-missing --cov-report=json:reports/tooling-coverage.json
	$(PY) scripts/check_repo.py coverage reports/tooling-coverage.json

kanban-check:
	$(NODE) --check scripts/kanban.mjs
	$(NODE) --test --experimental-test-coverage --test-coverage-include="scripts/kanban.mjs" --test-coverage-lines=90 --test-coverage-branches=85 tests/kanban.test.mjs
	$(NODE) scripts/kanban.mjs validate

architecture:
	$(PY) scripts/check_architecture.py

check: lint types kanban-check architecture
	$(PY) scripts/check_repo.py foundation
	$(MAKE) test

ci: check
	$(PY) scripts/check_repo.py product
	$(PY) -m mypy packages
	$(PY) -m scripts.run_product_ci

audit:
	mkdir -p reports
	$(PY) -m pip_audit --strict --cache-dir .cache/pip-audit -f json -o reports/dependency-audit.json

release: ci audit
	$(PY) scripts/check_repo.py release

hooks:
	git config --local core.hooksPath .githooks

layer: check
	$(PY) -m scripts.run_layer_ci $(L)

deploy-local:
	$(MAKE) layer L=1
	$(PY) -m s1router.deployment deploy

rollback-local:
	$(PY) -m s1router.deployment rollback

local-status:
	$(PY) -m s1router.deployment status

local-smoke:
	$(PY) -m scripts.local_smoke
