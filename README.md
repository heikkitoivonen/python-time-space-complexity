**English** | [简体中文](README.zh-CN.md)

# Python Big-O: Time & Space Complexity

[![Lint / Format](https://img.shields.io/github/actions/workflow/status/heikkitoivonen/python-time-space-complexity/deploy.yml?label=lint%20%2F%20format)](https://github.com/heikkitoivonen/python-time-space-complexity/actions/workflows/deploy.yml)
[![Type Check](https://img.shields.io/github/actions/workflow/status/heikkitoivonen/python-time-space-complexity/deploy.yml?label=type%20check)](https://github.com/heikkitoivonen/python-time-space-complexity/actions/workflows/deploy.yml)
[![Python](https://img.shields.io/badge/python-3.10%20to%203.14-blue)](https://www.python.org/)
[![License](https://img.shields.io/github/license/heikkitoivonen/python-time-space-complexity)](LICENSE.txt)
[![Docs](https://img.shields.io/badge/docs-pythoncomplexity.com-brightgreen)](https://pythoncomplexity.com)

A comprehensive resource documenting the time and space complexity of Python's built-in functions and standard library operations across different Python versions and implementations.

## Overview

This project provides detailed documentation of algorithmic complexity for:
- **Python Built-ins**: `list`, `dict`, `set`, `str`, etc.
- **Standard Library Modules**: `collections`, `heapq`, `bisect`, `annotationlib`, `compression.zstd`, and more
- **Python Versions**: 3.10–3.14 (including new 3.14 features)
- **Alternative Implementations**: CPython, PyPy, Jython, IronPython

## Features

- 📊 Comprehensive complexity tables for all major built-in types and operations
- 🔄 Version-specific behavior and optimization changes
- 🚀 Implementation-specific notes (CPython vs PyPy vs others)
- 🛠️ CLI Tool for estimating complexity of your own code
- 🔍 Interactive search and filtering
- 📱 Mobile-friendly responsive design

## Website

Visit the documentation at: [pythoncomplexity.com](https://pythoncomplexity.com)

---

## Quick Start

### Prerequisites
- Python 3.10+ (3.14 recommended)
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

## Install the Python Complexity Agent Skill

`python-complexity` gives agents an offline reference for Python builtin and
standard-library time and space complexity. It helps with code analysis,
performance reviews, and operation comparisons, including version and
implementation qualifications. It is independent of the skills used to maintain
this repository.

Download `python-complexity-<version>.zip` and `SHA256SUMS` from a
[Python Complexity skill release](https://github.com/heikkitoivonen/python-time-space-complexity/releases).
Choose a release tagged `python-complexity-v<version>`. Use the attached skill
ZIP: GitHub's automatic **Source code** archives and the source directory
`skills/python-complexity/` do not include generated references.

Extract the ZIP and place the entire `python-complexity` directory in one of
these locations. Create the parent directory if needed. Install in one scope
per agent to avoid duplicate copies.

| Agent | Personal installation | Project installation | Explicit use |
|-------|-----------------------|----------------------|--------------|
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `~/.agents/skills/python-complexity/` | `.agents/skills/python-complexity/` | `$python-complexity` followed by your question |
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills/python-complexity/` | `.claude/skills/python-complexity/` | `/python-complexity` followed by your question |
| [GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) | `~/.copilot/skills/python-complexity/` | `.github/skills/python-complexity/` | Ask Copilot to use the `python-complexity` skill |

`~` means your home directory; on Windows use the corresponding directory under
your user profile. Project paths are relative to the project where you want to
use the skill. Cloud agents need the project installation included in their
checkout; a personal directory on your computer does not transfer to the cloud.
The installed directory must contain `SKILL.md`, `manifest.json`, `LICENSE.txt`,
and `references/` directly. Reading the skill requires no Python, `uv`, Node.js,
or network access.

For example, on Linux or macOS, install version 1.0.0 for Codex from your download
directory:

```bash
mkdir -p ~/.agents/skills
unzip python-complexity-1.0.0.zip -d ~/.agents/skills
```

Compare the ZIP's SHA-256 with its entry in `SHA256SUMS` using `sha256sum` on
Linux, `shasum -a 256` on macOS, or `Get-FileHash -Algorithm SHA256` in PowerShell.
Start a new agent session and ask, for example: "Use python-complexity to analyze
the time and peak space complexity of this function, citing the reference."

### Update or Pin a Version

To update, replace the installed `python-complexity` directory with the complete
directory from a newer release, rather than merging files. To pin a version,
keep that release's ZIP and its checksum; the installed `manifest.json` records
the skill version, source revision, and supported Python versions.

### Uninstall

1. Find the installation directory in the agent table above. For example, a
   personal Codex installation is at `~/.agents/skills/python-complexity/`.
2. Delete that entire `python-complexity` directory, including its bundled
   references. Keep the parent `skills` directory and any other skills. If you
   installed copies in both personal and project locations, remove both.
3. Start a new agent session so it no longer uses the loaded skill instructions.

For a project installation tracked by Git, commit the directory removal to
propagate the uninstall to other checkouts. No package-manager uninstall command
is needed for a skill installed by extracting the ZIP.

## Development Commands

### Using Make (Recommended)

```bash
make help                # See all available commands
make install             # Install production dependencies
make dev                 # Install dev environment
make serve               # Serve documentation locally, all locales
make serve-en            # Serve English documentation only
make serve-one LOCALE=ja  # Serve one locale as it ships
make build               # Build all locales as separate sites
make build-en            # Build English documentation only
make check               # Run lint, types, skill validation, and tests
make lint                # Check lint and formatting
make format              # Format code and apply lint fixes
make types               # Run type checker
make test                # Run tests
make audit               # Report live documentation coverage
make skills-build        # Build offline skill in build/skills/
make skills-check        # Validate generated skill content and links
make skills-package      # Create release ZIPs and checksums in dist/skills/
make skills-eval         # Build skill and display manual evaluation prompts
make clean               # Remove site output and development caches
make update              # Update dependencies
```

### Using uv Directly

```bash
uv sync                    # Sync dependencies
uv run mkdocs serve        # Run command in venv
uv add package-name        # Add dependency
uv add --dev pytest-plugin # Add dev dependency
uv lock --upgrade          # Update dependencies
```

### Complexity Estimator CLI

Measure the Big-O complexity of your own Python functions:

```bash
# Usage: python scripts/estimate_complexity.py <module> <function>
python scripts/estimate_complexity.py my_script my_function
```

Example output:
```text
Input Size (n)  | Avg Time (s)
-----------------------------------
100             | 0.000003
500             | 0.000012
...
Estimated Complexity: O(n) (Linear)
```

---

## Project Structure

```
├── docs/                       # MkDocs documentation source
│   ├── index.md                # Landing page
│   ├── builtins/               # Built-in types (list, dict, set, tuple, str)
│   ├── stdlib/                 # Standard library modules
│   ├── implementations/        # CPython, PyPy, Jython, IronPython
│   └── versions/               # Python version guides (3.10–3.14)
├── skills/                     # Distributable agent skill sources and release guidance
│   ├── python-complexity/
│   │   ├── SKILL.md            # Agent instructions
│   │   └── version.txt         # Independent skill release version
│   ├── README.md               # Build and distribution guide
│   └── evaluations.md          # Manual agent evaluation prompts and rubric
├── .agents/skills/             # Repository-maintenance skills (not distributed)
├── scripts/                    # Utility scripts
│   └── build_skills.py         # Generate, validate, and package the offline skill
├── tests/                      # Documentation, complexity, and packaging tests
├── build/skills/               # Generated installable skill (Git-ignored)
├── dist/skills/                # Generated release ZIPs and checksums (Git-ignored)
├── .github/workflows/          # GitHub Actions CI/CD
│   ├── deploy.yml             # Documentation site checks and deployment
│   └── skills.yml             # Skill checks, preview artifacts, and releases
├── pyproject.toml              # Project metadata and dependencies
├── mkdocs.yml                  # MkDocs configuration
└── Makefile                    # Development commands
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
- **ruff** for linting (line length: 100 chars, Python 3.10+ compatibility)
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
| `sort()` | O(n log n) | Timsort/Powersort |

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
Python 3.10     ← Baseline
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

---

⭐ **Star this repository** if you found it useful — it helps others discover it.
