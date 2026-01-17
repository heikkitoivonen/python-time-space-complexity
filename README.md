# Python Time & Space Complexity

A comprehensive resource documenting the time and space complexity of Python's built-in functions and standard library operations across different Python versions and implementations.

## Overview

This project provides detailed documentation of algorithmic complexity for:
- **Python Built-ins**: `list`, `dict`, `set`, `str`, etc.
- **Standard Library Modules**: `collections`, `heapq`, `bisect`, `annotationlib`, `compression.zstd`, and more
- **Python Versions**: 3.9–3.14 (including new 3.14 features)
- **Alternative Implementations**: CPython, PyPy, Jython, IronPython

### Key Statistics
- **373 documented items** with 118% coverage
- **4 Python implementations** documented (CPython, PyPy, Jython, IronPython)
- **6 Python versions** documented (3.9–3.14)
- 199 stdlib modules documented

## Features

- 📊 Comprehensive complexity tables for all major built-in types and operations
- 🔄 Version-specific behavior and optimization changes
- 🚀 Implementation-specific notes (CPython vs PyPy vs others)
- 🔍 Interactive search and filtering
- 📱 Mobile-friendly responsive design

## Website

Visit the documentation at: [pythoncomplexity.com](https://pythoncomplexity.com)

---

## Quick Start

### Prerequisites
- Python 3.9+ (3.14 recommended)
- [uv](https://github.com/astral-sh/uv) - Fast Python package manager
- Git

### Installation

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
# Open http://localhost:8000
```

---

## Development Commands

### Using Make (Recommended)

```bash
make help      # See all available commands
make dev       # Install dev environment
make serve     # Serve documentation locally
make build     # Build static site
make check     # Run lint + types + tests
make lint      # Run linter
make format    # Format code
make types     # Run type checker
make test      # Run tests
make clean     # Clean build artifacts
make update    # Update dependencies
```

### Using uv Directly

```bash
uv sync                    # Sync dependencies
uv run mkdocs serve        # Run command in venv
uv add package-name        # Add dependency
uv add --dev pytest-plugin # Add dev dependency
uv lock --upgrade          # Update dependencies
```

---

## Project Structure

```
├── docs/                      # MkDocs documentation source
│   ├── index.md              # Landing page
│   ├── builtins/             # Built-in types (list, dict, set, tuple, str)
│   ├── stdlib/               # Standard library modules
│   ├── implementations/       # CPython, PyPy, Jython, IronPython
│   └── versions/             # Python version guides (3.9–3.14)
├── data/                      # JSON data files
│   ├── builtins.json
│   └── stdlib.json
├── scripts/                   # Utility scripts
│   └── audit_documentation.py
├── tests/                     # Test files
├── .github/workflows/         # GitHub Actions CI/CD
│   └── deploy.yml
├── pyproject.toml            # Project metadata and dependencies
├── mkdocs.yml                # MkDocs configuration
└── Makefile                  # Development commands
```

---

## Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/add-numpy-complexity
```

### 2. Make Changes & Test Locally
```bash
vim docs/new-module.md
make serve  # View at http://localhost:8000
```

### 3. Run Quality Checks
```bash
make lint    # Check code quality
make format  # Auto-format code
make types   # Type checking
make test    # Run tests
make check   # All checks (required before commit)
```

### 4. Commit & Push
```bash
git add .
git commit -m "Add: NumPy array complexity documentation"
git push origin feature/add-numpy-complexity
```

### Adding Documentation
1. Create markdown file in `docs/`
2. Add link to `mkdocs.yml` navigation
3. Test locally with `make serve`
4. Run `make check` before committing

---

## Code Quality Standards

### Linting & Formatting
- **ruff** for linting (line length: 100 chars, Python 3.9+ compatibility)
- **pyright** for static type checking
- **pytest** for testing

### Commit Messages
```
Type: Brief description

Types: Add, Fix, Update, Refactor, Docs, Test, Chore
Example: Add: List complexity documentation
```

---

## Quick Reference - Python Complexity Cheat Sheet

### Lists
| Operation | Time | Notes |
|-----------|------|-------|
| `append()` | O(1)* | Amortized |
| `insert(i)` | O(n) | Shifts elements |
| `pop()` | O(1) | Last element |
| `pop(0)` | O(n) | First element |
| `in` | O(n) | Linear search |
| `sort()` | O(n log n) | Timsort |

**Pro tip:** Use `deque.appendleft()` for O(1) prepend instead of `list.insert(0)`.

### Dictionaries & Sets
| Operation | Time |
|-----------|------|
| `d[key]` | O(1) avg |
| `d[key] = v` | O(1) avg |
| `key in d` | O(1) avg |
| `set.add()` | O(1) avg |
| `x in set` | O(1) avg |

**Pro tip:** Use sets for fast membership testing, not lists.

### Strings
| Operation | Time |
|-----------|------|
| `len()` | O(1) |
| `s[i]` | O(1) |
| `in` (substring) | O(n) avg |
| `split()` / `join()` | O(n) |

**Pro tip:** Use `"".join(list)` not `+=` in loops.

### Standard Library

| Module | Operation | Time |
|--------|-----------|------|
| **deque** | `append()` / `appendleft()` | O(1) |
| **deque** | `pop()` / `popleft()` | O(1) |
| **heapq** | `heapify()` | O(n) |
| **heapq** | `heappush()` / `heappop()` | O(log n) |
| **bisect** | `bisect_left/right()` | O(log n) |

### Common Patterns

```python
# ❌ Bad: O(n) membership check
if item in list: pass

# ✅ Good: O(1) membership check
if item in set: pass

# ❌ Bad: O(n²) string concatenation
result = ""
for item in items:
    result += item

# ✅ Good: O(n) string building
result = "".join(items)

# ❌ Bad: O(n) prepend
lst.insert(0, item)

# ✅ Good: O(1) prepend
from collections import deque
dq = deque()
dq.appendleft(item)
```

### Python Version Performance
```
Python 3.9      ← Baseline
Python 3.10     ← +5% improvements
Python 3.11     ← +10-60% improvements (inline caching!)
Python 3.12     ← +5-10% improvements
Python 3.13     ← Similar (experimental free-threading)
Python 3.14     ← Better GC pauses, new heapq max-heap
```

### Implementation Comparison
| Implementation | Use Case | Speed | GIL |
|---|---|---|---|
| CPython | Default, standard | Good | Yes |
| PyPy | CPU-bound loops | Excellent* | No |
| Jython | Java integration | Good | No |
| IronPython | .NET integration | Good | No |

---

## Deployment

### GitHub Pages Setup
1. Push to GitHub
2. Go to **Settings** → **Pages**
3. Select **Deploy from a branch** → **gh-pages**
4. GitHub Actions automatically deploys on push

### Custom Domain (Optional)
1. Update `site_url` in `mkdocs.yml`
2. Configure DNS to point to GitHub Pages
3. In GitHub Settings → Pages, enter custom domain
4. Enable HTTPS

---

## Troubleshooting

### Build Issues
```bash
make clean && make build
uv run mkdocs serve --verbose
```

### Dependency Issues
```bash
rm -rf .venv/ && uv sync
```

### GitHub Pages Not Updating
1. Check GitHub Actions tab for errors
2. Verify gh-pages branch exists
3. Wait ~1-2 minutes for deployment

---

## Sources & References

- [Python Official Documentation](https://docs.python.org/3/)
- [TimeComplexity Wiki](https://wiki.python.org/moin/TimeComplexity)
- [Python Enhancement Proposals (PEPs)](https://www.python.org/dev/peps/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [MkDocs Documentation](https://www.mkdocs.org/)
- [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - See [LICENSE.txt](LICENSE.txt) for details

## Disclaimer

While we strive for accuracy, complexity information may vary based on specific implementations and versions. Always verify with official documentation and benchmarks for performance-critical code.
