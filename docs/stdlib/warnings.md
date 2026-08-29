# warnings Module

The `warnings` module provides a framework for issuing and filtering warning messages in Python applications.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `warn()` | O(n) | O(1) | n = filters to check; includes stack inspection |
| `simplefilter()` | O(1) | O(1) | Prepends to filter list |
| Filter matching | O(n) | O(1) | n = filters; checked in order until match |

## Core Functions

### Issuing Warnings

```python
import warnings

# Issue a warning - O(n) for filter scan + stack inspection
warnings.warn("This is deprecated", DeprecationWarning)

# With stack level
warnings.warn("Use new_func() instead", DeprecationWarning, stacklevel=2)

# Custom message
warnings.warn("Resource leak detected", ResourceWarning)
```

### Filtering Warnings

```python
import warnings

# Ignore all deprecation warnings - O(1)
warnings.simplefilter("ignore", DeprecationWarning)

# Show all warnings - O(1)
warnings.simplefilter("always")

# Turn warnings into errors - O(1)
warnings.simplefilter("error", DeprecationWarning)

# Print each warning only once - O(1)
warnings.simplefilter("once")
```

### Advanced Filtering

```python
import warnings

# Custom filter - O(1) per filter
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("error", category=RuntimeWarning)

# Filter by message pattern
warnings.filterwarnings("ignore", message=".*deprecated.*")

# Filter by module
warnings.filterwarnings("ignore", module="old_module")
```

### Capturing Warnings

```python
import warnings

# Catch warnings as context manager
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    # Code that issues warnings
    
    # Check captured warnings - O(n)
    for warning in w:
        print(warning.category, warning.message)
```

## Warning Categories

### Exception Hierarchy

```python
Warning (base class)
├── DeprecationWarning
├── PendingDeprecationWarning
├── RuntimeWarning
├── SyntaxWarning
├── UserWarning (default)
├── FutureWarning
├── ImportWarning
├── UnicodeWarning
├── BytesWarning
├── ResourceWarning
└── EncodingWarning
```

### Common Filters

```python
import warnings

# Default - show each warning once - O(1)
warnings.simplefilter("default")

# Error - raise exception - O(1)
warnings.simplefilter("error")

# Ignore - suppress completely - O(1)
warnings.simplefilter("ignore")

# Always - show every occurrence - O(1)
warnings.simplefilter("always")

# Module - show once per module - O(1)
warnings.simplefilter("module")

# Once - show only first occurrence - O(1)
warnings.simplefilter("once")
```

## Practical Examples

### Deprecation Warnings

```python
import warnings

def old_function():
    warnings.warn(
        "old_function() is deprecated, use new_function() instead",
        DeprecationWarning,
        stacklevel=2
    )
    # Implementation
    pass

# Users can filter
warnings.filterwarnings("ignore", category=DeprecationWarning)
old_function()  # Won't print warning
```

### Runtime Warnings

```python
import warnings

def risky_operation():
    # O(n) in the filter list, plus stack inspection for stacklevel
    warnings.warn(
        "This operation may cause data loss",
        RuntimeWarning,
        stacklevel=2
    )

# Turn into error for critical code - O(1) to install, and it short-circuits
# the "once" registry, so every call now pays the full warn() cost
warnings.filterwarnings("error", category=RuntimeWarning)
try:
    risky_operation()
except RuntimeWarning as e:
    print(f"Operation blocked: {e}")
```

## Related Modules

- [logging Module](logging.md) - For log messages with categories
- [sys Module](sys.md) - Access to stderr for warnings output
