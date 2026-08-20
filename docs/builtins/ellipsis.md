# Ellipsis (...) Constant Complexity

The `Ellipsis` constant (also spelled `...`) is a singleton value used to represent an omitted value. It's commonly used in slicing, type hints, and other contexts where a placeholder is needed.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Access | O(1) | O(1) | Singleton object |
| Comparison | O(1) | O(1) | Identity check with `is` |
| Type check | O(1) | O(1) | `type(...)` |
| Assignment | O(1) | O(1) | Single object |
| Passing to `__getitem__` | O(1) | O(1) | `obj[...]` hands over the singleton; the type decides what it means |
| Hashing (dict key, set member) | O(1) | O(1) | Hashable singleton |

## Basic Usage

### Subscripting with Ellipsis

`...` is an ordinary object, and `obj[...]` simply passes it to
`obj.__getitem__`. What it means is entirely up to the type: the builtin
sequences reject it, while a type that opts in can give it any meaning.

```python
# O(1) - the subscript is just an object handed to __getitem__
data = [[1, 2, 3], [4, 5, 6]]

# Builtin sequences do not accept Ellipsis:
#   data[...]     TypeError: list indices must be integers or slices
#   data[1, ...]  TypeError: list indices must be integers or slices, not tuple

class Grid:
    """A type that gives Ellipsis a meaning."""

    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        if key is ...:        # O(1) - identity check against the singleton
            return self.rows  # "all of it"
        return self.rows[key]

grid = Grid(data)
grid[...]  # O(1) - [[1, 2, 3], [4, 5, 6]]
grid[0]    # O(1) - [1, 2, 3]
```

### Placeholder in Code

```python
# O(1) - ellipsis as placeholder
def incomplete_function():
    """Function stub - O(1)"""
    ...  # O(1) - valid placeholder

# vs pass
def with_pass():
    pass

# Both are valid, ... is more modern and can hold meaning
result = incomplete_function()  # None
```

### Type Hints

```python
# O(1) - ellipsis in type hints
from typing import Callable

# Function that takes any arguments
def flexible(*args: int) -> None:
    """Function with variable args - O(1)"""
    pass

# Callback type with ellipsis
callback: Callable[..., int]  # O(1) - function with any args, returns int

# Variable-length tuple: any number of ints, all the same type
def total(values: tuple[int, ...]) -> int:
    """Sum a tuple of any length - O(n)"""
    return sum(values)
```

## Complexity Details

### Singleton Pattern

```python
# O(1) - ellipsis is a singleton
ellipsis1 = ...
ellipsis2 = Ellipsis

# Both are same object
print(ellipsis1 is ellipsis2)  # True - O(1)
print(... is Ellipsis)  # True - O(1)

# Identity check
print(id(...) == id(Ellipsis))  # True - O(1)
```

### Type Information

```python
# O(1) - type of ellipsis
value = ...

# Type checking
type(value)  # <class 'ellipsis'> - O(1)

# Type identity
type(value) is type(...)  # True - O(1)

# Cannot create new instances
# new_ellipsis = Ellipsis()  # TypeError
```

### Truthiness

```python
# O(1) - ellipsis is truthy
if ...:  # O(1)
    print("Ellipsis is truthy")  # This executes

# Use explicit checks
if ... is ...:  # O(1) - always true (both are Ellipsis)
    print("Ellipsis")
```

## Performance Patterns

### vs None as Placeholder

`None` is the usual "no value" sentinel, which makes it ambiguous when `None`
is itself a legitimate argument. `...` is a distinct singleton, so it can mean
"not supplied" without colliding with a real value.

```python
# O(1) - Ellipsis as a sentinel that None cannot be confused with
MISSING = ...

def get(mapping, key, default=MISSING):
    """Look up a key, distinguishing 'no default' from 'default is None'."""
    if key in mapping:            # O(1) average
        return mapping[key]       # O(1) average
    if default is MISSING:        # O(1) - identity check
        raise KeyError(key)
    return default

data = {"a": 1, "b": None}
get(data, "b")            # None - the stored value
get(data, "z", None)      # None - the supplied default
# get(data, "z")          # KeyError - no default was supplied
```

## Common Use Cases

### Function Stubs

```python
# O(1) - placeholder in development
class Logger:
    def debug(self, msg):
        ...  # TODO: implement
    
    def info(self, msg):
        ...  # TODO: implement
    
    def error(self, msg):
        print(f"ERROR: {msg}")

# O(1) - use stub
logger = Logger()
logger.debug("test")  # Does nothing (ellipsis)
logger.info("test")   # Does nothing (ellipsis)
logger.error("test")  # Prints error
```

### Abstract Methods

```python
# O(1) - ellipsis in abstract base classes
from abc import ABC, abstractmethod

class DataStore(ABC):
    @abstractmethod
    def save(self, data):
        ...  # O(1) - placeholder for abstract method
    
    @abstractmethod
    def load(self, key):
        ...  # O(1) - placeholder
```

The `...` bodies are what matters here: `@abstractmethod` already prevents
instantiation, so the body only needs to be syntactically valid.

### Variable-Length Tuple Types

`tuple[X, ...]` is the standard way to annotate a homogeneous tuple of any
length. The ellipsis here means "more of the same", not "any type".

```python
# O(1) - the annotations themselves are just objects
from typing import get_args

Row = tuple[int, ...]   # any number of ints
Pair = tuple[int, int]  # exactly two

def widen(row: Row) -> Row:
    """Double every value - O(n)"""
    return tuple(v * 2 for v in row)

# O(1) - the ellipsis is preserved in the type's arguments
get_args(Row)   # (<class 'int'>, Ellipsis)
get_args(Pair)  # (<class 'int'>, <class 'int'>)
```

### Callable Type Hints

```python
# O(1) - ellipsis in type annotations
from typing import Any, Callable, TypeVar

T = TypeVar('T')

# Function accepting any arguments and returning anything
flexible_func: Callable[..., Any]  # O(1)

# Callback with fixed return type
callback: Callable[..., int]  # O(1) - any args, returns int

# More specific callable
specific_func: Callable[[int, str], bool]  # O(1) - specific signature
```

### Slice Objects

```python
# O(1) - ellipsis in slice objects
class CustomSequence:
    def __getitem__(self, key):
        if key is ...:  # O(1) - check for ellipsis
            # Return everything
            return self.all_items()
        elif isinstance(key, slice):  # O(1)
            # Handle slice
            return self.slice_items(key)
        else:  # O(1)
            return self.get_item(key)

# O(1) - use custom sequence
seq = CustomSequence()
result = seq[...]    # Returns all
result = seq[1:3]    # Returns slice
result = seq[0]      # Returns single
```

## Advanced Usage

### Protocol Placeholders

```python
# O(1) - ellipsis in protocol definitions
from typing import Protocol

class IterableProtocol(Protocol):
    def __iter__(self):
        ...  # O(1) - placeholder

class SizedProtocol(Protocol):
    def __len__(self):
        ...  # O(1) - placeholder
```

Protocol bodies are never executed, so `...` is the conventional filler.

## Practical Examples

### Data Structure with Ellipsis

```python
# O(1) - ellipsis as sentinel in data structures
class Matrix:
    def __init__(self, shape: tuple):
        self.shape = shape
        self.data = None
    
    def __getitem__(self, key):
        # Handle various indexing with ellipsis
        if key is ...:  # O(1)
            return self.data  # All elements
        elif isinstance(key, tuple) and ... in key:  # O(1)
            # Handle ellipsis in tuple of indices
            idx = key.index(...)  # O(n)
            return self._slice_with_ellipsis(key)
        else:
            return self.data[key]

# O(1) - flexible indexing
matrix = Matrix((3, 4, 5))
all_data = matrix[...]      # All elements
last_dim = matrix[..., 0]   # All but last dimension
```

## Edge Cases

### Ellipsis in Collections

```python
# O(1) - store ellipsis in collections
items = [1, 2, ..., 3, 4]  # O(1)

# Check for ellipsis
for item in items:  # O(n)
    if item is ...:  # O(1)
        print("Found ellipsis")

# Dictionary with ellipsis
mapping = {1: 'a', ...: 'rest', 2: 'b'}  # O(1)
value = mapping[...]  # O(1) - 'rest'
```

### Comparison with Ellipsis

```python
# O(1) - comparison always identity
... == ...      # True  - O(1)
... is ...      # True  - O(1)

# Comparing with other values
... == None     # False - O(1)
... == 0        # False - O(1)
... == False    # False - O(1)

# Always use 'is' for ellipsis
if value is ...:  # O(1) - correct
    print("Is ellipsis")
```

## Best Practices

✅ **Do**:

- Use `...` for function stubs during development
- Use in abstract base classes as placeholders
- Use for "all remaining" in slicing contexts
- Use in type hints for flexible signatures: `Callable[..., T]`
- Use `is ...` for identity checks (not equality)
- Document when ellipsis is used as sentinel

❌ **Avoid**:

- Using `== ...` (use `is ...` instead)
- Confusing with unpacking operator `*`
- Returning ellipsis from production functions
- Using instead of `NotImplemented` in dunder methods
- Mixing ellipsis with None when they differ semantically
- Using in regular function bodies instead of `pass`

## Related Constants

- **[None](none.md)** - Null value
- **[NotImplemented](notimplemented.md)** - Operation not implemented marker
- **[True](true.md)** - Boolean true
- **[False](false.md)** - Boolean false

## Version Notes

- **Python 2.x**: Ellipsis available, limited uses
- **Python 3.x**: Enhanced support in type hints and slicing
- **Python 3.9+**: Extended unpacking syntax improves ... usage
- **Python 3.11+**: Variadic generics use ellipsis more extensively
