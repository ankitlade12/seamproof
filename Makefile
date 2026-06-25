.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help install lint test check demo gate-pass gate-fail clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install the package with dev extras
	$(PY) -m pip install -e ".[dev]"

lint: ## Run ruff
	$(PY) -m ruff check src tests

test: ## Run the test suite
	$(PY) -m pytest

check: lint test ## Lint and test

demo: ## Run the gate against every example trace
	@for t in examples/traces/*.json; do \
		echo "==> $$t"; \
		seamproof check -c contracts -t $$t --no-fail; \
		echo; \
	done

gate-pass: ## Gate the golden trace (expect exit 0)
	seamproof check -c contracts -t examples/traces/golden_happy_path.json

gate-fail: ## Gate an injected failure (expect exit 1)
	seamproof check -c contracts -t examples/traces/seam1_amount_mismatch.json

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
