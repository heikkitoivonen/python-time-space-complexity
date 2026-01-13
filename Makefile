.PHONY: help install dev serve build lint format check clean test audit

help:
	@echo "Python Time & Space Complexity - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install dependencies with uv"
	@echo "  make dev         Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make serve       Serve docs locally (http://localhost:8000)"
	@echo "  make build       Build static site"
	@echo ""
	@echo "Quality:"
	@echo "  make lint        Run ruff linter"
	@echo "  make format      Format code with ruff"
	@echo "  make check       Run lint and type checks"
	@echo "  make test        Run tests with pytest"
	@echo "  make audit       Audit documentation coverage"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean       Remove build artifacts and cache"
	@echo "  make update      Update dependencies"

install:
	uv sync --no-dev

dev:
	uv sync

serve:
	uv run mkdocs serve

build:
	uv run mkdocs build

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

check: lint test

test:
	uv run pytest

audit:
	uv run python scripts/audit_documentation.py

clean:
	rm -rf site/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

update:
	uv lock --upgrade
