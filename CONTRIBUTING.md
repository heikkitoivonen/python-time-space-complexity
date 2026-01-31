# Contributing to Python Time & Space Complexity

Thank you for interest in contributing! This guide will help you get started.

## How to Contribute

### Report Inaccuracies

Found an error in complexity analysis? Open an issue with:
- The operation or module affected
- What the documentation says vs what's correct
- Source or evidence (Python docs, implementation, benchmark results)

### Add Documentation

Help us expand coverage for:
- More stdlib modules (`itertools`, `functools`, `json`, etc.)
- Additional built-in functions
- Implementation-specific details
- Version-specific behavior

### Improve Existing Content

- Clarify explanations
- Add more examples
- Fix typos or formatting
- Add performance tips

## Process

1. **Fork** the repository
2. **Create branch**: `git checkout -b feature/what-you-add`
3. **Make changes** following guidelines below
4. **Test locally**: `mkdocs serve`
5. **Submit PR** with clear description

## Documentation Style Guide

### File Structure

```
docs/
├── section/
│   ├── index.md      # Overview
│   └── item.md       # Details
```

### Complexity Table Format

```markdown
| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `method()` | O(n) | O(1) | Brief description |
```

### Code Examples

```python
# Clear, runnable examples
def example():
    lst = [1, 2, 3]
    lst.append(4)  # O(1)
```

### Admonitions

For important notes:

```markdown
!!! warning "Warning Title"
    Warning content

!!! tip "Tip Title"
    Tip content

!!! note "Note Title"
    Note content
```

## Content Guidelines

### Complexity Standards

- Always include time complexity
- Include space complexity when relevant
- Note amortized vs worst-case
- Reference Python version differences

### Accuracy Requirements

- Source official Python documentation
- Verify with CPython implementation if possible
- Test claims with actual benchmarks
- Cite sources for non-obvious complexity

### Examples

- Show realistic use cases
- Compare with alternatives when helpful
- Explain why certain approaches are preferred
- Include both good and bad patterns

## Building Locally

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Serve documentation
make serve

# Visit http://localhost:8000
```

## Commit Messages

Use clear, descriptive messages:

```
Add: Complexity analysis for collections.deque

Fix: Incorrect complexity for string.replace()

Update: Python 3.12 performance notes

Docs: Improve list.insert() explanation
```

## PR Description Template

```markdown
## What This Changes

Brief description of changes.

## Why

Explain the motivation.

## Type of Change

- [ ] New content
- [ ] Bug fix
- [ ] Documentation improvement
- [ ] Structure/organization

## Related Issues

Closes #(issue number) if applicable
```

## Review Process

- At least one review before merge
- Verify accuracy with sources
- Check consistency with style guide
- Test local build works

## Questions?

Open an issue with your question. We're here to help!

## License

By contributing, you agree your work is licensed under MIT (same as project).

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Assume good faith
- Report violations to maintainers

Thank you for helping make Python complexity documentation better!