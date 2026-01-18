# Ellipsis (...) Constant Complexity

The `Ellipsis` constant (also spelled `...`) is a singleton value used to represent an omitted value. It's commonly used in slicing, type hints, and other contexts where a placeholder is needed.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Access | O(1) | O(1) | Singleton object |
| Comparison | O(1) | O(1) | Identity check with `is` |
| Type check | O(1) | O(1) | `type(...)` |
| Assignment | O(1) | O(1) | Single object |
| Indexing with | O(1) | O(1) | Slice with `...` |

## Basic Usage

### Multi-Dimensional Slicing

```python
# O(1) - ellipsis represents remaining dimensions
import numpy as np

array = np.arange(24).reshape(2, 3, 4)

# Standard slicing
slice1 = array[0, :, :]  # First element, all of rest

# Using ellipsis
slice2 = array[0, ...]   # O(1) - same as above, cleaner
slice3 = array[..., 0]   # O(1) - all elements, first in last dim

# Equivalent:
# array[...] == array[:, :, :]  - O(1)
# array[0, ...] == array[0, :, :]  - O(1)
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

# Array shape annotation
def process_array(arr: "np.ndarray[..., np.float64]") -> None:
    """Process array of any shape - O(1)"""
    pass
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

```python
# Ellipsis - O(1) signal for "all remaining"
def slice_dims(arr, *indices):
    # Use ... for remaining dimensions
    if ... in indices:  # O(k) - k = len(indices)
        # Handle remaining dimensions
        pass

# vs None - different meaning
def slice_with_none(arr, *indices):
    # None means "new axis" in slicing
    # Different semantic
    pass

# Ellipsis is clearer for "remaining" semantics
```

### Slice Operations

```python
# O(1) - ellipsis in slicing
array = [[1, 2, 3], [4, 5, 6]]

# Standard slicing
result = array[:]  # Full array

# With ellipsis (equivalent but clearer intent)
result = array[...]  # O(1) - "all of it"

# Multi-dimensional
matrix = [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
result = matrix[1, ...]  # O(1) - second element, all nested
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

# Subclass must implement
class FileStore(DataStore):
    def save(self, data):
        with open('file.txt', 'w') as f:
            f.write(data)
    
    def load(self, key):
        with open('file.txt', 'r') as f:
            return f.read()
```

### NumPy Array Slicing

```python
# O(n) - use ellipsis with NumPy
import numpy as np

# 4D array
array = np.arange(120).reshape(2, 3, 4, 5)

# Get all but last dimension - all elements in last
result = array[..., 0]  # O(n) - shape (2, 3, 4)

# Get specific slice, then all remaining
result = array[1, ..., 2]  # O(n) - shape (3, 4)

# Equivalent to:
# array[1, :, :, 2]  - O(n)
# But ... is cleaner for unknown dimensions
```

### Callable Type Hints

```python
# O(1) - ellipsis in type annotations
from typing import Callable, TypeVar

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

# Concrete implementation
class MyCollection:
    def __iter__(self):
        return iter([1, 2, 3])
    
    def __len__(self):
        return 3
```

### Variadic Generic Types

```python
# O(1) - ellipsis in generic variadic types (Python 3.11+)
from typing import TypeVarTuple, Unpack

Shape = TypeVarTuple('Shape')

class Array:
    def __init__(self, shape: tuple[Unpack[Shape]]):
        self.shape = shape

# O(1) - allows any shape tuple
arr1 = Array((10,))        # 1D
arr2 = Array((10, 20))     # 2D
arr3 = Array((10, 20, 30)) # 3D
```

### Default Implementation

```python
# O(1) - ellipsis as default placeholder
class Interface:
    def method1(self):
        ...  # Abstract
    
    def method2(self):
        ...  # Abstract
    
    def method3(self):
        print("Default implementation")

# Subclass overrides what's needed
class Implementation(Interface):
    def method1(self):
        return "Implemented 1"
    
    def method2(self):
        return "Implemented 2"
    
    # Inherits method3's default
```

## Practical Examples

### API Stub

```python
# O(1) - create API stub with ellipsis
class APIClient:
    def get_user(self, user_id: int) -> dict:
        ...  # TODO: Implement API call
    
    def create_user(self, data: dict) -> dict:
        ...  # TODO: Implement
    
    def delete_user(self, user_id: int) -> bool:
        ...  # TODO: Implement

# Later, implement actual calls
class RealAPIClient(APIClient):
    def get_user(self, user_id: int) -> dict:
        # Real implementation
        return requests.get(f"/users/{user_id}").json()
    
    def create_user(self, data: dict) -> dict:
        return requests.post("/users", json=data).json()
    
    def delete_user(self, user_id: int) -> bool:
        return requests.delete(f"/users/{user_id}").status_code == 204
```

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

### Partial Application

```python
# O(1) - ellipsis in functional programming
from functools import partial

def calculate(a, b, c, d):
    return a + b + c + d

# Create partial with ellipsis (conceptual)
# In practice, use functools.partial
partial_calc = partial(calculate, 1)

# More flexible approach
def flexible_args(*args):
    # Accepts any number of args
    return sum(args)

result = flexible_args(1, 2, 3, 4)  # 10
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

### Unpacking with Ellipsis

```python
# O(n) - unpacking with ellipsis (Python 3.9+)
a, *middle, b = [1, 2, 3, 4, 5]
# a=1, middle=[2,3,4], b=5

# Ellipsis is not unpacking operator
# But can use in type hints for variadic
def flexible(*args: int) -> None:
    # args can have any number of ints
    pass
```

## Performance Considerations

### vs None as Placeholder

```python
# Both O(1) but different semantics
UNKNOWN = None
REMAINING = ...

# Using None (ambiguous)
def process(value=None):
    if value is None:  # O(1) - is this "not provided" or "actually None"?
        use_default()

# Using ... (clear)
def process(value=...):
    if value is ...:  # O(1) - clearly "not provided, use default"
        use_default()
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
