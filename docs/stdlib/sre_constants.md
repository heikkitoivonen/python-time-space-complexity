# sre_constants Module

The `sre_constants` module defines constants used internally by the regex engine and the sre_compile/sre_parse modules.

!!! warning "Internal module"
    `sre_constants` is an internal implementation detail of `re` and is not part of
    the public API. Prefer using `re` for regex operations.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Access constant | O(1) | O(1) | Static constants |
| Lookup opcode | O(1) | O(1) | Attribute lookup |

## Regex Engine Constants

### Using Regex Constants

```python
import sre_constants

# Access opcodes - O(1)
print(sre_constants.LITERAL)      # Regular character
print(sre_constants.BRANCH)       # | operator
print(sre_constants.RANGE)        # Character range [a-z]

# View all constants (implementation details)
for name in dir(sre_constants):
    if name.isupper():
        print(f"{name}: {getattr(sre_constants, name)}")
```

## Related Documentation

- [re Module](re.md)
- [sre_compile Module](sre_compile.md)
- [sre_parse Module](sre_parse.md)
