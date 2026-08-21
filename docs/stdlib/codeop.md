# codeop Module

The `codeop` module provides utilities for compiling Python source code incrementally, useful for interactive interpreters.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `compile_command()` | O(n) | O(n) | n = source length |
| Syntax checking | O(n) | O(1) | Single pass |

## Incremental Compilation

### Checking Code Completion

```python
import codeop

# Check if code is complete - O(n)
result = codeop.compile_command('print("hello")')
print(type(result))  # <code object>

# Incomplete code returns None
result = codeop.compile_command('if True:')
print(result)  # None

# Syntax error raises exception
try:
    codeop.compile_command('if True')
except SyntaxError as e:
    print(f"Syntax error: {e}")
```

## Related Documentation

- [ast Module](ast.md)
- [compile() Function](../builtins/compile.md)
