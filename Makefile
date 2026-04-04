.PHONY: install lint format typecheck test test-cov check

install:
	uv sync

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
