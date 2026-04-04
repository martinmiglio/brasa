.PHONY: setup install lint format typecheck test test-cov check

setup:
	uv sync
	uv run pre-commit install

install: setup

lint:
	uv run ruff check src/

format:
	uv run ruff format src/

typecheck:
	uv run ty check src/

test:
	uv run pytest

test-cov:
	uv run pytest --cov=brasa

check: lint typecheck test
