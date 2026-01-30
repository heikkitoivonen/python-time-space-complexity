# pdb Module

The `pdb` module provides an interactive debugger for Python code, allowing breakpoints, stepping, and inspection of variables.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `set_trace()` | Varies | O(1) | Setup is O(1); interactive runtime is program/user dependent |
| Breakpoint | O(1) to register | O(1) | Hit checks occur during program execution |
| Step/continue | Varies | O(1) | Runs until next stop; depends on code executed |

## Interactive Debugging

### Setting Breakpoints

```python
import pdb

def buggy_function(x):
    # Enter debugger (setup is O(1); runtime depends on program/user)
    pdb.set_trace()
    
    result = x * 2
    return result

# When called, drops into interactive debugger
# Commands: n=next, s=step, c=continue, l=list, p=print
```

### Post-Mortem Debugging

```python
import pdb
import traceback

try:
    1 / 0
except Exception:
    # Debug after exception (setup is O(1); runtime depends on session)
    pdb.post_mortem()
```

## Related Documentation

- [traceback Module](traceback.md)
- [inspect Module](inspect.md)
