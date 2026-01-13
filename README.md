# Python Time & Space Complexity

A comprehensive resource documenting the time and space complexity of Python's built-in functions and standard library operations across different Python versions and implementations.

## Overview

This project provides detailed documentation of algorithmic complexity for:
- **Python Built-ins**: `list`, `dict`, `set`, `str`, etc.
- **Standard Library Modules**: `collections`, `heapq`, `bisect`, and more
- **Multiple Python Versions**: CPython 3.8+
- **Alternative Implementations**: CPython, PyPy, Jython, IronPython

## Features

- 📊 Comprehensive complexity tables for all major built-in types and operations
- 🔄 Version-specific behavior and optimization changes
- 🚀 Implementation-specific notes (CPython vs PyPy vs others)
- 🔍 Interactive search and filtering
- 📱 Mobile-friendly responsive design

## Website

Visit the documentation at: [pythoncomplexity.com](https://pythoncomplexity.com)

## Repository Structure

```
├── docs/                      # MkDocs documentation source
│   ├── index.md              # Landing page
│   ├── builtins/             # Built-in types and functions
│   ├── stdlib/               # Standard library modules
│   ├── implementations/       # Python implementation details
│   └── versions/             # Version-specific guides
├── tests/                     # Test suite
├── scripts/                   # Utility scripts
│   ├── generate_docs.py      # Documentation generation template
│   └── validate_data.py      # Data validation template
├── pyproject.toml            # Project metadata and dependencies
├── mkdocs.yml                # MkDocs configuration
├── Makefile                  # Development commands
├── .github/
│   └── workflows/
│       └── deploy.yml        # GitHub Pages deployment
└── UV_SETUP.md              # Detailed uv setup guide
```

## Getting Started

### Requirements

- Python 3.8+ (3.11+ recommended)
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager

### Quick Start

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and set up
git clone https://github.com/heikkitoivonen/python-time-space-complexity.git
cd python-time-space-complexity

# Install dependencies
uv sync

# Start development server
make serve
# or
uv run mkdocs serve

# Open http://localhost:8000
```

### Common Commands

```bash
# Install with dev tools
make dev

# Serve documentation locally
make serve

# Build static site
make build

# Run linter
make lint

# Format code
make format

# Run tests
make test

# See all commands
make help
```

### Build

```bash
# Build static site
make build

# Output goes to site/ directory
```

## Development

### Setup

```bash
# Install dependencies with uv
uv sync

# Activate virtual environment (optional)
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows
```

### Testing

```bash
# Run all tests
make test
# or
uv run pytest

# Run specific test
uv run pytest tests/test_example.py
```

### Code Quality

```bash
# Check for issues
make lint

# Fix formatting
make format

# Run all checks
make check
```

### Adding Dependencies

```bash
# Add a production dependency
uv add package-name

# Add a dev dependency
uv add --dev pytest-plugin

# Update all dependencies
uv lock --upgrade
```

See [UV_SETUP.md](UV_SETUP.md) for detailed uv setup and workflows.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Sources & References

- [Python Official Documentation](https://docs.python.org/3/)
- [TimeComplexity Wiki](https://wiki.python.org/moin/TimeComplexity)
- [Python Enhancement Proposals (PEPs)](https://www.python.org/dev/peps/)
- Implementation source code repositories

## License

MIT License - See [LICENSE](LICENSE) for details

## Disclaimer

While we strive for accuracy, complexity information may vary based on specific implementations and versions. Always verify with official documentation and benchmarks for performance-critical code.
