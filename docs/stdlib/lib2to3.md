# lib2to3 Module

⚠️ **REMOVED IN PYTHON 3.13**: The `lib2to3` module and `2to3` tool were deprecated in Python 3.11 and removed in Python 3.13.

The `lib2to3` module provided tools for converting Python 2 code to Python 3, using a refactoring framework with syntax tree transformations.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Parse code | O(n) | O(n) | n = source length |
| Apply refactorings | O(n) | O(n) | n = tree nodes |
| Generate output | O(n) | O(n) | n = modified code |

## Converting Python 2 to 3

### Using 2to3 Tool

```bash
# Legacy command-line usage (Python <= 3.12)
2to3 -w script.py          # Convert in place
2to3 -d script.py          # Dry run (show diffs)
2to3 -f all script.py      # Apply all fixers
2to3 -x print script.py    # Skip print fixer
```

### Programmatic Conversion

```python
# Legacy API usage (Python <= 3.12)
from lib2to3 import refactor

# Create refactoring tool - O(1)
tool = refactor.RefactoringTool(
    ['lib2to3.fixes.fix_print',
     'lib2to3.fixes.fix_imports']
)

# Refactor file - O(n)
refactored = tool.refactor_file('oldcode.py', write=True)
```

## Related Documentation

- [ast Module](ast.md)
- [tokenize Module](tokenize.md)
