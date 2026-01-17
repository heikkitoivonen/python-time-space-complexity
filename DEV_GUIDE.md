# Developer Guide

This guide covers development workflow, testing, and quality standards for this project.

## Prerequisites

- Python 3.9+ (3.14 recommended)
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager

## Quick Setup

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone https://github.com/heikkitoivonen/python-time-space-complexity.git
cd python-time-space-complexity

# Install all dependencies (including dev tools)
uv sync
```

## Development Commands

### Using Make (Recommended)

```bash
# Help - see all available commands
make help

# Install dev environment
make dev

# Serve documentation locally
make serve

# Build static site
make build

# Check code quality (lint + tests)
make check

# Run linter
make lint

# Format code
make format

# Run type checker
make types

# Run tests
make test

# Clean build artifacts and cache
make clean

# Update dependencies
make update
```

### Using uv Directly

```bash
# Sync dependencies
uv sync

# Run command in virtual environment
uv run python script.py
uv run mkdocs serve

# Add dependency
uv add package-name
uv add --dev pytest-plugin

# Update dependencies
uv lock --upgrade

# View installed packages
uv pip list
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/add-numpy-complexity
```

### 2. Make Changes

```bash
# Edit documentation
vim docs/new-module.md

# Update config
vim mkdocs.yml
```

### 3. Test Locally

```bash
# Serve and view in browser
make serve
# Visit http://localhost:8000

# In another terminal, run checks
make lint
make test
```

### 4. Format Code

```bash
# Auto-format code and fix issues
make format
```

### 5. Type Check

```bash
# Check for type errors
make types
```

### 6. Commit Changes

```bash
git add .
git commit -m "Add: NumPy array complexity documentation"
```

### 7. Push and Create PR

```bash
git push origin feature/add-numpy-complexity
# Then create PR on GitHub
```

## Code Quality Standards

### Linting

Project uses [ruff](https://github.com/astral-sh/ruff) for linting.

```bash
# Check for issues
make lint
# or
uv run ruff check .

# Fix issues
uv run ruff check --fix .
```

Configuration in `pyproject.toml`:
- Line length: 100 characters
- Python 3.9+ compatibility
- Checks: pycodestyle, pyflakes, isort, comprehensions, bugbear, upgrades

### Formatting

```bash
# Format code
make format
# or
uv run ruff format .

# This includes:
# - Code formatting (ruff format)
# - Auto-fixes (ruff check --fix)
# - Import sorting (isort)
```

### Type Checking

Project uses [pyright](https://github.com/microsoft/pyright) for static type checking.

```bash
# Check type errors
make types
# or
uv run pyright

# Output shows:
# - Number of type errors, warnings, and informations
# - File-by-file breakdown
# - Detailed error messages with line numbers
```

Configuration in `pyproject.toml`:
- Strict type checking enabled
- Python 3.9+ compatibility
- Detects unused imports, undefined variables, type mismatches

### Testing

Project uses [pytest](https://pytest.org/) for testing.

```bash
# Run all tests
make test
# or
uv run pytest

# Run specific test file
uv run pytest tests/test_documentation.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=src
```

## Documentation Structure

### Adding a New Module

1. Create markdown file in appropriate directory:
   ```bash
   vim docs/stdlib/new_module.md
   ```

2. Add complexity table:
   ```markdown
   | Operation | Time | Notes |
   |-----------|------|-------|
   | func() | O(n) | Description |
   ```

3. Include examples:
   ```markdown
   ## Examples

   ```python
   # Example code
   ```
   ```

4. Update navigation in `mkdocs.yml`:
   ```yaml
   - stdlib/new_module.md
   ```

5. Test locally:
   ```bash
   make serve
   ```

### Markdown Best Practices

- Use headers for structure (h2 for sections, h3 for subsections)
- Include complexity tables for all operations
- Add code examples for major concepts
- Link to related topics
- Use admonitions for important notes:
  ```markdown
  !!! warning "Title"
      Content
  ```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run specific test
uv run pytest tests/test_documentation.py::test_data_files_exist

# Run with verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x

# Run only tests matching pattern
uv run pytest -k "data"
```

### Writing Tests

Tests are in `tests/` directory:

```python
# tests/test_example.py
def test_something():
    """Test description."""
    assert condition
```

See `tests/test_documentation.py` for existing test patterns.

## Dependencies

### Adding Dependencies

```bash
# Add production dependency
uv add package-name

# Add dev dependency
uv add --dev pytest-plugin

# This updates:
# - pyproject.toml
# - uv.lock
# - .venv/
```

### Updating Dependencies

```bash
# Update all dependencies
uv lock --upgrade

# Update specific package
uv add --upgrade package-name

# Check outdated packages
uv pip list
```

### Dependency Management

Dependencies declared in `pyproject.toml`:

```toml
[project]
dependencies = [
    "mkdocs>=1.5.0",
    "mkdocs-material>=9.4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "ruff>=0.1.0",
]
```

## Pre-commit Checks

Before committing:

```bash
# Run all checks
make check

# This includes:
# - Linting (ruff check)
# - Type checking (pyright)
# - Tests (pytest)
```

Or run individually:

```bash
make lint   # Code quality checks
make types  # Type error checks
make test   # Run tests
```

## Documentation

### Building Documentation

```bash
# Build static site
make build

# Output in site/ directory

# Serve locally during development
make serve
```

### Configuration

MkDocs configuration in `mkdocs.yml`:
- Site name, URL, theme
- Navigation structure
- Extensions and plugins
- Search configuration

Material theme documentation: https://squidfunk.github.io/mkdocs-material/

## Environment Variables

Optional environment variables for development:

```bash
# Set Python version for uv
export UV_PYTHON=3.14

# Set virtual environment location
export VIRTUAL_ENV=.venv

# Enable verbose output
export RUST_LOG=debug
```

## Troubleshooting

### Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf .venv/
uv sync

# Or force with uv
uv venv --force
```

### Dependency Conflicts

```bash
# Clear lock and regenerate
rm uv.lock
uv lock

# Check why package is needed
uv pip show package-name
```

### Build Failures

```bash
# Clean and rebuild
make clean
make build

# Check for errors
uv run mkdocs serve --verbose
```

## Performance Tips

### Local Development

```bash
# Use --no-strict to skip version verification (faster)
# See uv docs for more options
```

### Testing

```bash
# Run tests in parallel
uv run pytest -n auto  # Requires pytest-xdist

# Run only changed tests
uv run pytest --lf  # Last failed
uv run pytest --ff  # Failed first
```

## Git Workflow

### Commit Messages

Follow conventional commits:

```
type(scope): description

- Add: New feature
- Fix: Bug fix
- Docs: Documentation
- Refactor: Code restructuring
- Test: Test additions
- Chore: Maintenance
```

### Branch Naming

```
feature/add-numpy-docs
fix/list-complexity-typo
docs/improve-readme
```

## Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [ruff Documentation](https://docs.astral.sh/ruff/)
- [pytest Documentation](https://docs.pytest.org/)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [pyproject.toml Specification](https://packaging.python.org/en/latest/specifications/pyproject-toml/)

## Questions?

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines or open an issue on GitHub.
