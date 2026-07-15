.PHONY: install dev lint test build

install:
	pip install .

dev:
	pip install -e ".[dev]"

lint:
	ruff check .

test:
	pytest -q

build:
	python -m build
