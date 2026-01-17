# Pprint Module Complexity

The `pprint` module provides a way to pretty-print Python data structures with consistent formatting.

## Common Operations

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `pprint(obj)` | O(n) | O(n) | Pretty print object |
| `pformat(obj)` | O(n) | O(n) | Format to string |
| `PrettyPrinter()` | O(1) | O(1) | Create formatter |
| `saferepr(obj)` | O(n) | O(n) | Safe repr; handles circular references |

## Pretty Printing

### pprint()

#### Time Complexity: O(n)

Where n = total elements in structure.

```python
from pprint import pprint

# Print nested dict: O(n) where n = total items
data = {
    'users': [
        {'name': 'Alice', 'age': 30},
        {'name': 'Bob', 'age': 25},
    ],
    'count': 2
}
pprint(data)  # O(n) to format and print

# Print large list: O(n)
large_list = list(range(10000))
pprint(large_list)  # O(n)
```

#### Space Complexity: O(n)

```python
from pprint import pprint

# Formatted output buffered
pprint({'a': [1, 2, 3] * 1000})  # O(n) space for output
```

### pformat()

#### Time Complexity: O(n)

```python
from pprint import pformat

# Format to string: O(n) where n = elements
formatted = pformat(data)  # O(n)

# Can control width
formatted = pformat(data, width=40)  # O(n) - reformat
formatted = pformat(data, depth=2)   # O(n) - limit depth
```

#### Space Complexity: O(n)

```python
from pprint import pformat

# Result string stored
result = pformat(large_dict)  # O(n) space
```

## Custom Formatting

### PrettyPrinter Class

#### Time Complexity: O(1) init, O(n) per format

```python
from pprint import PrettyPrinter

# Create formatter: O(1)
pp = PrettyPrinter(
    indent=2,
    width=80,
    depth=None,
    compact=False,
    sort_dicts=True,
)  # O(1)

# Format with printer: O(n)
pp.pprint(data)  # O(n)

# Get formatted string: O(n)
formatted = pp.pformat(data)  # O(n)
```

#### Space Complexity: O(1) + O(n)

```python
from pprint import PrettyPrinter

pp = PrettyPrinter(width=80)  # O(1) space
formatted = pp.pformat(data)  # O(n) space for result
```

## Safe Representations

### saferepr()

#### Time Complexity: O(n)

```python
from pprint import saferepr

# Safe repr handles circular references: O(n)
data = {'self': None}
data['self'] = data  # Circular reference

safe = saferepr(data)  # O(n) - doesn't infinite loop
```

#### Space Complexity: O(n)

```python
from pprint import saferepr

# Result string
safe = saferepr(large_data)  # O(n) space
```

## Common Patterns

### Pretty Print With Width Control

```python
from pprint import pprint

# Narrow width: more lines, better for narrow terminals
pprint(data, width=40)

# Wide width: fewer lines
pprint(data, width=120)

# Auto-fit to terminal
import shutil
width = shutil.get_terminal_size().columns
pprint(data, width=width)
```

### Limit Depth for Large Structures

```python
from pprint import pprint

# Limit depth to avoid huge output
data = {f'key_{i}': {f'nested_{j}': j for j in range(100)} for i in range(100)}

# Deep structure - avoid printing all
pprint(data, depth=1)  # Only show first level
# Output: {'key_0': {...}, 'key_1': {...}, ...}

# Show 2 levels
pprint(data, depth=2)  # Shows keys and first nested level
```

### Debug Complex Data Structures

```python
from pprint import pformat

def process_data(data):
    """Process and debug data."""
    result = calculate(data)
    
    # Use pformat for logging
    print(f"Result:\n{pformat(result)}")
    
    return result
```

### Format for Output/Logging

```python
from pprint import pformat
import logging

logger = logging.getLogger(__name__)

def log_data(data):
    """Log formatted data."""
    formatted = pformat(data)  # O(n)
    logger.debug(f"Data:\n{formatted}")
```

## Performance Characteristics

### Best Practices

```python
from pprint import pprint, pformat

# Good: Control output size
pprint(data, depth=2)  # Limit depth
pprint(data, width=80)  # Fit to width

# Good: Use pformat for strings
output = pformat(data)  # Store formatted
print(output)

# Avoid: pprint on huge structures
huge_data = [list(range(100000)) for _ in range(100)]
pprint(huge_data)  # O(n) - can be slow!

# Better: Limit with depth/width
pprint(huge_data, depth=1, width=80)
```

### Memory Considerations

```python
from pprint import pprint, pformat

# pformat creates string: O(n) memory
large_dict = {f'key_{i}': i for i in range(1000000)}
formatted = pformat(large_dict)  # O(n) memory

# pprint writes incrementally (still O(n) internally)
import sys
pprint(large_dict, stream=sys.stderr)  # O(n) memory
```

## Comparison with repr()

```python
# Built-in repr()
repr(data)  # O(n) - compact, single line

# pprint
from pprint import pformat
pformat(data)  # O(n) - formatted, multiple lines

# Both O(n), pformat is more readable
```

## Configuration

```python
from pprint import PrettyPrinter

# Compact output (Python 3.8+)
pp = PrettyPrinter(compact=True)

# Sort dictionary keys
pp = PrettyPrinter(sort_dicts=True)

# Indent level
pp = PrettyPrinter(indent=4)

# Recursion depth limit
pp = PrettyPrinter(depth=3)
```

## Version Notes

- **Python 3.2+**: `compact` parameter added
- **Python 3.10+**: Better formatting improvements

## Related Documentation

- [Reprlib Module](reprlib.md) - Alternative repr()
- [Inspect Module](inspect.md) - Object introspection
