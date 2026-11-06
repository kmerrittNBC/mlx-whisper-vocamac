.PHONY: check test lint format

check: lint test

test:
	uv run --group dev pytest -q

lint:
	uv run --group dev ruff check .
	uv run --group dev ruff format --check .

format:
	uv run --group dev ruff check --fix .
	uv run --group dev ruff format .
