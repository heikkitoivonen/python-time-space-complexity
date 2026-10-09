# callable() Function Complexity

The `callable()` function checks whether an object is callable (can be invoked with arguments).
It reads one slot on the object's type rather than looking up `__call__` by name, so its cost
does not depend on the object's attributes or the depth of its class hierarchy.

## Complexity Analysis

| Case | Time | Space | Notes |
|------|------|-------|-------|
| Check callable status | O(1) | O(1) | Reads the call slot on `type(obj)`; no attribute lookup |
| Object with `__call__` | O(1) | O(1) | `__call__` must be defined on the class or a base; one set on the instance is ignored |
| Built-in types | O(1) | O(1) | Every class is callable: its metaclass fills the slot |

## Basic Usage

### Checking Functions and Methods

```python
# O(1) - constant time check
def my_function():
    pass

callable(my_function)      # True
callable(len)              # True
callable("hi".upper)       # True (bound method)
callable(str.split)        # True (method descriptor)
```

### Checking Non-Callable Objects

```python
# O(1) - returns False
callable(42)               # False
callable("string")         # False
callable([1, 2, 3])        # False
callable({"key": "value"}) # False
callable(None)             # False
```

### Classes and Instances

```python
# O(1) - classes are callable
class MyClass:
    pass

callable(MyClass)          # True (can instantiate)

instance = MyClass()
callable(instance)         # False (unless __call__ defined)

# With __call__ method
class Callable:
    def __call__(self):
        return "called"

obj = Callable()
callable(obj)              # True (has __call__)
```

## Complexity Details

### How callable() Works

`callable()` never looks `__call__` up by name. It reads the call slot on `type(obj)`, which
Python fills when the class or one of its bases defines `__call__`, so `__getattr__` and
`__getattribute__` are never called. A `__call__` set on the instance does not count, which is
why `hasattr(obj, "__call__")` is not an equivalent:

```python
class Plain:
    pass

obj = Plain()
obj.__call__ = lambda: "instance attribute"
assert hasattr(obj, "__call__")
assert not callable(obj)  # O(1) - the instance attribute is ignored

Plain.__call__ = lambda self: "class attribute"
assert callable(obj)  # O(1) - the class now fills the slot
```

### A True Result Does Not Promise a Successful Call

`callable()` only says the type has a call slot. The call can still fail, for example on the
wrong arguments or when the class sets `__call__` to something that is not callable:

```python
class Broken:
    __call__ = None

assert callable(Broken())  # O(1) - the slot is filled

try:
    Broken()()
except TypeError as e:
    assert "not callable" in str(e)
else:
    raise AssertionError("expected TypeError")
```

## Common Patterns

### Function Dispatch

```python
# O(1) - check before calling
def execute_if_callable(func, *args):
    if callable(func):
        return func(*args)
    else:
        return func

result = execute_if_callable(len, [1, 2, 3])  # 3
value = execute_if_callable(42)  # 42
```

### Callback Validation

```python
# O(1) - validate callback parameter
def register_callback(callback):
    if not callable(callback):
        raise TypeError(f"callback must be callable, got {type(callback)}")
    # Register callback
    return callback

# Valid
register_callback(lambda x: x + 1)  # OK

# Invalid
try:
    register_callback(42)  # TypeError
except TypeError as e:
    print(e)
```

### Polymorphic Processing

```python
# O(n) for n items, plus the cost of each call
def process(items):
    results = []
    for item in items:
        if callable(item):  # O(1)
            results.append(item())  # Call it
        else:
            results.append(item)    # Use as-is
    return results

values = [42, lambda: 100, "string", dict]
assert process(values) == [42, 100, "string", {}]
```

## Callables in Python

### Functions

```python
# All are callable O(1)

# Regular function
def func():
    pass
callable(func)  # True

# Lambda
f = lambda x: x + 1
callable(f)  # True

# Built-in function
callable(len)  # True
callable(print)  # True

# Method
obj = "hello"
callable(obj.upper)  # True
```

### Classes

```python
# O(1) - classes are callable (they instantiate)

class MyClass:
    pass

callable(MyClass)  # True

# Built-in types
callable(int)      # True
callable(str)      # True
callable(list)     # True
callable(dict)     # True
```

### Objects with __call__

```python
# O(1) - check for __call__ method

class Callable:
    def __call__(self):
        return "I was called"

obj = Callable()
callable(obj)  # True

result = obj()  # "I was called"
```

## Performance Patterns

### vs isinstance() Checks

```python
# Both O(1), but different purposes
import types

obj = lambda x: x + 1

# callable() - high level
if callable(obj):
    pass

# isinstance() - more specific
if isinstance(obj, types.FunctionType):
    pass

# callable() is cleaner for just checking if callable
```

### Batch Processing

```python
# O(n) - check n items
# n calls to callable(), each O(1)

items = [42, lambda: 1, "str", len, [1, 2]]
callables = [x for x in items if callable(x)]
# O(n) total - [<lambda>, len]
```

## Edge Cases

### Partially Applied Functions

```python
from functools import partial

# O(1) - partial objects are callable
add_five = partial(lambda x, y: x + y, 5)
callable(add_five)  # True

result = add_five(10)  # 15
```

### Class Methods and Static Methods

```python
# O(1) - each method, looked up on the class, is callable

class Example:
    @classmethod
    def class_method(cls):
        return "class"
    
    @staticmethod
    def static_method():
        return "static"
    
    def instance_method(self):
        return "instance"

callable(Example.class_method)      # True
callable(Example.static_method)     # True
callable(Example.instance_method)   # True
```

### Generators and Iterators

```python
# O(1) - functions are callable, but generators are not

def generator():
    yield 1

callable(generator)     # True (it's the function)
callable(generator())   # False (generator object not callable)

# Generator object has __iter__ and __next__, not __call__
```

### Built-in Types

```python
# O(1) - type check

class NotType:
    pass

# Instances - not callable
instance = NotType()
callable(instance)  # False

# Class - callable
callable(NotType)  # True
```

## Practical Examples

### Lazy Evaluation

```python
# O(1) - check if value or factory
def lazy_value(obj):
    if callable(obj):
        return obj()  # Call factory
    else:
        return obj    # Return value directly

# Usage
value1 = lazy_value(42)              # 42
value2 = lazy_value(lambda: 42)      # 42 (factory called)

# Useful for configuration
def expensive_calculation():
    return sum(range(1_000))

config = {
    'static': 100,
    'dynamic': lambda: expensive_calculation()
}

for key, val in config.items():
    print(f"{key}: {lazy_value(val)}")
```

### Function Composition

```python
# O(1) - validate functions before composing
def compose(f, g):
    if not (callable(f) and callable(g)):
        raise TypeError("Both arguments must be callable")
    
    return lambda x: f(g(x))

square = lambda x: x ** 2
double = lambda x: x * 2

composed = compose(square, double)
result = composed(5)  # (5 * 2) ** 2 = 100
```

### Event Handler Registration

```python
# O(1) - validate event handler
class EventManager:
    def __init__(self):
        self.handlers = []
    
    def register(self, handler):
        if not callable(handler):
            raise TypeError("Handler must be callable")
        self.handlers.append(handler)
    
    def emit(self, event):
        for handler in self.handlers:
            handler(event)

manager = EventManager()
manager.register(lambda e: print(f"Event: {e}"))
manager.emit("click")  # Output: Event: click
```

## Best Practices

✅ **Do**:

- Use `callable()` to check before invoking unknown objects
- Check in callback/handler validation
- Document which parameters should be callable
- Use in defensive programming

❌ **Avoid**:

- Assuming objects are callable without checking
- Using `callable()` for type discrimination (use `isinstance()` for that)
- Overcomplicating with `__call__` when simple functions work
- Adding unnecessary `callable()` checks in performance-critical code

## Related Functions

- **[hasattr()](hasattr.md)** - Check for attribute existence
- **[isinstance()](isinstance.md)** - Check object type
- **[type()](type_func.md)** - Get object type
- **[inspect.isfunction()](https://docs.python.org/3/library/inspect.html)** - Detailed type checking

## Version Notes

- **Python 2.x**: `callable()` available as built-in
- **Python 3.0-3.1**: Removed (controversial decision)
- **Python 3.2+**: Re-added as built-in
- **All versions**: O(1) constant time operation
