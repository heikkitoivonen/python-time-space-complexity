# sre_parse Module

The `sre_parse` module parses regular expression patterns into an abstract syntax tree used by the regex engine.

!!! warning "Internal module"
    `sre_parse` is an internal implementation detail of `re` and is not part of the
    public API. Prefer using `re` for regex operations.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Parse pattern | O(n) | O(n) | n = pattern length |
| Build AST | O(n) | O(n) | n = pattern complexity |

## Parsing Regex Patterns

### Analyzing Regex Structure

```python
import sre_parse

# Parse pattern - O(n)
pattern = r'\d+@[\w.-]+\.\w+'
ast = sre_parse.parse(pattern)

# Examine structure - O(1)
print(ast)
# Shows the parse tree

# Pattern analysis
for item in ast:
    print(f"Token: {item}")
```

## Related Documentation

- [re Module](re.md)
- [sre_compile Module](sre_compile.md)
- [sre_constants Module](sre_constants.md)
