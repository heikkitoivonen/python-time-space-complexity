.PHONY: help install dev serve serve-en build build-en lint format types check clean test audit

# Address for the dev server. Override for a non-default setup, e.g.
#   make serve DEV_ADDR=0.0.0.0:5005
DEV_ADDR ?= 127.0.0.1:8000

# The i18n plugin builds every locale as a full pass over the whole site, so
# each extra language costs about as much as the English build. Setting this
# to false leaves only English, which is what the -en targets do.
EN_ONLY := BUILD_ALL_LOCALES=false

help:
	@echo "Python Big-O: Time & Space Complexity - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install dependencies with uv"
	@echo "  make dev         Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make serve       Serve docs locally, all locales (http://localhost:8000)"
	@echo "  make serve-en    Serve English only - much faster, for most local work"
	@echo "  make build       Build static site, all locales"
	@echo "  make build-en    Build English only - much faster, for most local work"
	@echo "                   Override the address with DEV_ADDR=host:port"
	@echo ""
	@echo "Quality:"
	@echo "  make lint        Run ruff linter"
	@echo "  make format      Format code with ruff"
	@echo "  make types       Run pyright type checker"
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
	uv run mkdocs serve --dev-addr $(DEV_ADDR)

serve-en:
	$(EN_ONLY) uv run mkdocs serve --dev-addr $(DEV_ADDR)

build:
	uv run mkdocs build

build-en:
	$(EN_ONLY) uv run mkdocs build

lint:
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

types:
	uv run pyright

check: lint types test

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
