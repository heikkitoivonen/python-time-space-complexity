# typing Module Complexity

The `typing` module provides support for type hints, allowing developers to annotate function parameters and return types for better code documentation and static analysis.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Type annotation | O(1) | O(1) | Define hint (no runtime check) |
| `get_type_hints()` | O(k) | O(k) | k = number of annotations; involves string evaluation |
| Type checking with `isinstance()` | O(1) | O(1) | Runtime check (limited) |
| Generic type creation | O(1) | O(1) | Create parameterized type |

## Basic Type Hints

### Function Annotations

```python
from typing import Optional, List

# Type hints - O(1) (no runtime overhead)
def greet(name: str) -> str:
    return f"Hello, {name}"

# Optional type - O(1)
def find_user(user_id: int) -> Optional[str]:
    # May return str or None
    if user_id == 1:
        return "Alice"
    return None

# List type - O(1)
def sum_numbers(nums: List[int]) -> int:
    return sum(nums)

# Hints are just annotations, no enforcement
greet(123)  # Works! (type checker would complain)
```

### Common Types

```python
from typing import Dict, Tuple, Set, Union

# Dict - key and value types - O(1)
def process_config(config: Dict[str, int]) -> None:
    pass

# Tuple - element types - O(1)
def get_coordinates() -> Tuple[float, float]:
    return (0.0, 1.0)

# Set - element type - O(1)
def get_unique_ids(data: List[str]) -> Set[str]:
    return set(data)

# Union - multiple possible types - O(1)
def parse_input(value: Union[str, int]) -> str:
    return str(value)
```

## Generic Types

### Generic Functions

```python
from typing import TypeVar, Generic

# TypeVar - represents any type - O(1)
T = TypeVar('T')

# Generic function - O(1)
def first(items: List[T]) -> T:
    return items[0]

# Usage - preserves type
numbers = [1, 2, 3]
first_num: int = first(numbers)  # Typed as int

strings = ["a", "b"]
first_str: str = first(strings)  # Typed as str
```

### Generic Classes

```python
from typing import Generic, TypeVar

# Type variable - O(1)
T = TypeVar('T')

# Generic class - O(1)
class Stack(Generic[T]):
    def __init__(self):
        self.items: List[T] = []
    
    def push(self, item: T) -> None:  # O(1)
        self.items.append(item)
    
    def pop(self) -> T:  # O(1)
        return self.items.pop()

# Usage
int_stack: Stack[int] = Stack()
int_stack.push(1)
int_stack.push(2)
```

## Callable Types

### Function Types

```python
from typing import Callable

# Callable type - O(1)
def apply_operation(a: int, b: int, op: Callable[[int, int], int]) -> int:
    return op(a, b)

# Pass functions - O(1)
def add(x: int, y: int) -> int:
    return x + y

result = apply_operation(5, 3, add)  # 8
```

### Higher-Order Functions

```python
from typing import Callable, List

# Return function - O(1)
def create_multiplier(factor: int) -> Callable[[int], int]:
    def multiply(x: int) -> int:
        return x * factor
    return multiply

# Usage
times_three = create_multiplier(3)  # O(1)
result = times_three(5)  # 15
```

## Union and Optional

### Union Types

```python
from typing import Union

# Union - multiple types - O(1)
def process_value(value: Union[int, str, float]) -> None:
    if isinstance(value, int):
        print(f"Integer: {value}")
    elif isinstance(value, str):
        print(f"String: {value}")
    else:
        print(f"Float: {value}")

# Works with any of the types
process_value(42)      # Integer
process_value("hello") # String
process_value(3.14)    # Float
```

### Optional (Union with None)

```python
from typing import Optional

# Optional[T] is Union[T, None] - O(1)
def find_item(items: List[str], target: str) -> Optional[str]:
    try:
        return items[items.index(target)]
    except ValueError:
        return None

# Usage
result = find_item(["a", "b", "c"], "b")  # str or None
```

## Type Aliases

### Creating Type Aliases

```python
from typing import List, Tuple, Dict

# Type alias - O(1)
Coordinate = Tuple[float, float]
Grid = List[List[int]]
Config = Dict[str, str]

# Use aliases - cleaner code
def get_location() -> Coordinate:
    return (0.0, 1.0)

def create_grid() -> Grid:
    return [[1, 2], [3, 4]]

# Aliases improve readability
def load_config(path: str) -> Config:
    return {"key": "value"}
```

## Type Hints in Practice

### Class Annotations

```python
from typing import List, Optional

class User:
    # Class-level annotations - O(1)
    name: str
    age: int
    email: Optional[str]
    
    def __init__(self, name: str, age: int, email: Optional[str] = None):
        self.name = name
        self.age = age
        self.email = email
    
    def get_info(self) -> str:
        return f"{self.name} ({self.age})"

# Usage
user = User("Alice", 30, "alice@example.com")
```

### Method Annotations

```python
from typing import List

class DataProcessor:
    def __init__(self):
        self.data: List[int] = []
    
    def add_value(self, value: int) -> None:
        self.data.append(value)
    
    def get_sum(self) -> int:
        return sum(self.data)
    
    def get_average(self) -> float:
        if not self.data:
            return 0.0
        return self.get_sum() / len(self.data)
```

## Runtime Type Checking

### Getting Type Hints

```python
from typing import get_type_hints

def add(a: int, b: int) -> int:
    return a + b

# Get hints - O(k) where k = number of hints
hints = get_type_hints(add)  # O(1)
# Result: {'a': <class 'int'>, 'b': <class 'int'>, 'return': <class 'int'>}

# Check hint
if hints.get('a') == int:
    print("Parameter 'a' is int")
```

### Runtime Enforcement

```python
from typing import get_type_hints

def validate_types(func):
    """Decorator to check types at runtime - O(k)"""
    hints = get_type_hints(func)  # O(k)
    
    def wrapper(*args, **kwargs):
        # Check arguments - O(n) where n = number of args
        for i, arg in enumerate(args):
            arg_names = list(hints.keys())
            if i < len(arg_names):
                arg_name = arg_names[i]
                expected_type = hints[arg_name]
                
                if not isinstance(arg, expected_type):
                    raise TypeError(f"{arg_name} must be {expected_type}")
        
        return func(*args, **kwargs)
    
    return wrapper

@validate_types
def add(a: int, b: int) -> int:
    return a + b

add(5, 3)      # OK
add(5, "3")    # TypeError
```

## Advanced Typing

### Protocol (Structural Typing)

```python
from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:
    def draw(self) -> None:
        print("Drawing circle")

class Square:
    def draw(self) -> None:
        print("Drawing square")

def render(obj: Drawable) -> None:
    obj.draw()

render(Circle())    # Works (implements draw)
render(Square())    # Works (implements draw)
```

### Generic with Constraints

```python
from typing import TypeVar

# TypeVar with constraints - O(1)
Number = TypeVar('Number', int, float)

def process_number(value: Number) -> Number:
    return value * 2

process_number(5)      # int
process_number(3.14)   # float
# process_number("5")  # Type error
```

## Performance Considerations

### Type Hints Have No Runtime Cost

```python
# Type hints are annotations only (O(1) overhead)
def with_hints(x: int, y: int) -> int:
    return x + y

def without_hints(x, y):
    return x + y

# Both have identical performance
# Type hints don't add runtime overhead
```

### Runtime Type Checking Can Be Expensive

```python
# Simple check - O(1)
if isinstance(value, int):
    pass

# Complex type check - O(n) for complex types
from typing import get_type_hints

hints = get_type_hints(func)  # O(k) where k = number of hints

# Avoid repeated hint retrieval (cache it)
hints = get_type_hints(func)  # O(k) once
for arg in args:
    if isinstance(arg, hints['param']):  # O(1) per check
        pass
```

## Best Practices

### Code Examples

```python
from typing import List, Optional, Dict, Callable

# Good: Clear types - O(1)
def process_data(
    items: List[int],
    processor: Callable[[int], int],
    config: Optional[Dict[str, str]] = None
) -> List[int]:
    """Process items with given processor."""
    return [processor(item) for item in items]

# Bad: No types
def process_data(items, processor, config=None):
    """Process items with given processor."""
    return [processor(item) for item in items]

# Use type hints for better code documentation and IDE support
```

## Version Notes

- **Python 3.5+**: Basic type hints support
- **Python 3.6+**: Variable annotations
- **Python 3.9+**: Can use `list[int]` instead of `List[int]`
- **Python 3.10+**: Union with `|` syntax: `int | None`

## Related Modules

- **pydantic** - Runtime type validation (external)
- **[dataclasses](dataclasses.md)** - Type hints for data classes
- **collections.abc** - Abstract base classes

## Best Practices

✅ **Do**:

- Use type hints for function parameters and returns
- Use `Optional[T]` for nullable values
- Use generic types for collections
- Use type aliases for complex types
- Include type hints in public APIs

❌ **Avoid**:

- Over-annotating (use when helpful)
- Assuming type hints are enforced (they're not)
- Using `Any` excessively (defeats purpose)
- Enforcing types at runtime (performance cost)
- Forgetting that hints are documentation only
