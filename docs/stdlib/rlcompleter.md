# rlcompleter Module

The `rlcompleter` module provides command-line completion for the Python interactive interpreter using readline.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `Completer()` | O(1) | O(1) | Create completer |
| `complete(text, state)` | O(n) | O(k) | n = namespace size; scans for matches |

## Readline Completion

### Interactive Completion Setup

```python
import readline
import rlcompleter

# Create completer - O(1)
completer = rlcompleter.Completer()

# Install completer - O(1)
readline.set_completer(completer.complete)

# Enable tab completion - O(1)
readline.parse_and_bind('tab: complete')

# In Python interactive mode:
# >>> import math
# >>> math.<TAB>  # Shows completions
```

## Related Documentation

- [readline Module](readline.md)
- [code Module](code.md)
