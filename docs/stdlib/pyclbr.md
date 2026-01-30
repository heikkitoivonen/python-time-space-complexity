# pyclbr Module

The `pyclbr` module reads a Python source file and provides information about the classes and functions defined in it without executing the code.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `readmodule()` | O(n) | O(n) | n = source lines |
| Parse definitions | O(n) | O(n) | Extract classes/functions |

## Analyzing Python Code Structure

### Getting Class and Function Info

```python
import pyclbr

# Parse module - O(n)
classes = pyclbr.readmodule('mymodule')

# Inspect results - O(1)
for classname, obj in classes.items():
    print(f"Class: {classname}")
    print(f"  Methods: {list(obj.methods.keys())}")
    print(f"  Line: {obj.lineno}")
```

### Finding Functions

```python
import pyclbr

# Read with functions - O(n)
classes = pyclbr.readmodule('script', path=['.'])
symbols = pyclbr.readmodule_ex('script', path=['.'])

# Examine
for name, obj in symbols.items():
    if isinstance(obj, pyclbr.Function):
        print(f"Function: {name} at line {obj.lineno}")
    else:
        print(f"Class: {name} at line {obj.lineno}")
```

## Related Documentation

- [inspect Module](inspect.md)
- [ast Module](ast.md)
