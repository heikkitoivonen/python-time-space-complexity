.PHONY: help install dev serve serve-en serve-one build build-en lint format types check clean test audit

# Address for the dev server. Override for a non-default setup, e.g.
#   make serve DEV_ADDR=0.0.0.0:5005
DEV_ADDR ?= 127.0.0.1:8000

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
	@echo "  make serve-one   Serve one locale as it ships, e.g. LOCALE=ja"
	@echo "  make build       Build all locales, each self-contained"
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

# Preview one locale exactly as it ships, its own search index included.
# Each locale is a self-contained site, so building one costs about a quarter
# of the total, which is what this and the -en targets exploit for local work.
# Refuses to guess: an empty BUILD_ONLY_LOCALE means "every locale", which
# would quietly serve the shared-index build this target exists to avoid.
serve-one:
ifndef LOCALE
	$(error LOCALE is required, e.g. make serve-one LOCALE=ja)
endif
	BUILD_ONLY_LOCALE=$(LOCALE) uv run mkdocs serve --dev-addr $(DEV_ADDR)

serve-en:
	@$(MAKE) --no-print-directory serve-one LOCALE=en

build:
	uv run python scripts/build_site.py

build-en:
	uv run python scripts/build_site.py en

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
