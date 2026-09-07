.PHONY: install dev lint test build help setup run format analyze

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

install: ## Install the package
	pip install .

dev: ## Editable install with dev dependencies
	pip install -e ".[dev]"

lint: ## Run the whole gate — every hook, every file
	pre-commit run --all-files

test: ## Run pytest
	pytest -q

build: ## Build sdist and wheel
	python -m build

setup: ## Install the pre-commit hook
	pre-commit install

run: ## Run k8s-rightsizer-report
	k8s-rightsizer-report --help

format: ## Rewrite the sources to canonical form
	ruff format .

analyze: ## Type-check the package
	basedpyright
