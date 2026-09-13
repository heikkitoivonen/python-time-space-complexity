# globals() and locals() Functions Complexity

The `globals()` and `locals()` functions return the current global and local
namespaces. `globals()` is the frame's own globals dict: the module's, or the
mapping handed to `exec()`. `locals()` is the namespace itself at module or
class scope, and a snapshot of the frame inside a function, built on every
call.

## Complexity Reference

Let `m` be the number of local variables in the calling function.

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `globals()` | O(1) | O(1) | Returns the frame's globals dict itself; writes reach that namespace |
| `locals()` at module or class scope | O(1) | O(1) | The namespace itself; writes reach it |
| `locals()` in a function | O(m²) from Python 3.13, O(m) before | O(m) | A snapshot; writes do not reach the function. From 3.13 each of the `m` names is found by a linear scan of the frame |
| `frame.f_locals` of a function frame | O(1) from Python 3.13, O(m) before | O(1) from 3.13, O(m) before | A live write-through proxy from 3.13; a snapshot dict before. Copying the proxy with `dict()` costs O(m²) |
| Accessing dict value | O(1) avg | O(1) | Dict key lookup; O(n) worst case with collisions |

## Understanding Namespaces

### Global Namespace

```python
# Access global namespace - O(1)
x = 10
y = 20

global_vars = globals()  # O(1) - returns reference to existing dict
print(global_vars['x'])  # O(1) - access value
print(global_vars['y'])  # O(1)

# Built-in names are not module globals
print('print' in globals())  # False
print('__builtins__' in globals())  # True - how the module reaches the builtins
```

### Local Namespace

```python
# Access local namespace - a snapshot per call
def my_func():
    a = 1
    b = 2
    
    local_vars = locals()  # O(m²) from Python 3.13, O(m) before - builds a dict
    print(local_vars['a'])  # O(1)
    print(local_vars['b'])  # O(1)
    
    return local_vars

result = my_func()
```

## Common Patterns

### Inspecting Variables

```python
# List all global variables - O(n)
x = 10
y = 20
z = 30

# Filter out dunder names - O(n); globals() itself is O(1)
my_vars = {k: v for k, v in globals().items()
           if not k.startswith('_')}

print(my_vars)  # {'x': 10, 'y': 20, 'z': 30}
```

### Dynamic Variable Access

```python
# Access variable by name - O(1)
var_name = 'x'
x = 42

# Using globals()
value = globals()[var_name]  # O(1) - get value

# Using getattr for objects
class Config:
    timeout = 30
    retries = 3

config = Config()
attr_name = 'timeout'
value = getattr(config, attr_name)  # O(1)
```

### Getting Caller's Locals

```python
import inspect

def get_caller_locals():
    """Get local variables of calling function"""
    # Get calling frame
    frame = inspect.currentframe().f_back  # O(1)
    
    # From Python 3.13 f_locals is a live proxy, O(1) to obtain and
    # O(m²) to copy; before 3.13 it is a snapshot dict, O(m)
    caller_locals = dict(frame.f_locals)
    
    return caller_locals

def caller():
    x = 10
    y = 20
    
    caller_vars = get_caller_locals()
    print(caller_vars)  # {'x': 10, 'y': 20}

caller()
```

## Function Scope

### Module Level

```python
# At module level, locals() == globals() - O(1)
X = 100

print(locals() is globals())  # True at module level
print(locals()['X'])  # O(1)
```

### Inside Functions

```python
# Inside function, locals() is different
global_x = 10

def func():
    local_y = 20
    
    # Different namespaces; each locals() call builds its snapshot first
    print('local_y' in locals())   # True - O(1) lookup
    print('local_y' in globals())  # False - O(1)
    print('global_x' in locals())  # False - O(1) lookup
    print('global_x' in globals()) # True - O(1)

func()
```

## Modifying Namespaces

### Setting Global Variables

```python
# Modify global namespace - O(1)
globals()['new_var'] = 100  # O(1)

print(new_var)  # 100 - variable created!

# Better approach: use globals() sparingly
# Prefer explicit assignment
new_var2 = 200
```

### Setting Local Variables

```python
# Modifying locals() has limited effect
def func():
    locals()['x'] = 10  # O(1) - sets a key in the snapshot only
    
    try:
        print(x)  # NameError! - x not actually in local scope
    except NameError:
        print("x not in local variables")

func()

# Don't use locals() to set variables in function
# Use explicit assignment instead
def func2():
    x = 10  # Proper way
    print(x)  # Works
```

## Practical Examples

### Debug Function State

```python
def debug_state(func_locals):
    """Print local variables with types"""
    print("Local variables:")
    
    for name, value in func_locals.items():  # O(m)
        if not name.startswith('_'):  # Skip special vars
            print(f"  {name}: {type(value).__name__} = {value}")

def example_func():
    x = 42
    s = "hello"
    lst = [1, 2, 3]
    
    debug_state(locals())  # O(m²) from Python 3.13, O(m) before

example_func()
```

### Serialize Local Variables

```python
import json

def save_state(local_data):
    """Save a function's locals() snapshot to JSON"""
    # Filter serializable objects - O(m)
    serializable = {}
    for k, v in local_data.items():
        if isinstance(v, (int, str, float, list, dict)):
            serializable[k] = v
    
    return json.dumps(serializable)

def task():
    count = 10
    name = "task"
    items = [1, 2, 3]
    
    # locals() is this frame's snapshot: O(m²) from Python 3.13, O(m) before
    state = save_state(locals())
    return state

print(task())  # {"count": 10, "name": "task", "items": [1, 2, 3]}
```

### Configuration Registry

```python
# Use globals() as simple registry - O(1) per lookup/update
CONFIG = {}

def register_config(name, value):
    """Register configuration"""
    globals()[f'config_{name}'] = value  # O(1)

def get_config(name):
    """Get configuration"""
    return globals().get(f'config_{name}')  # O(1)

# Usage
register_config('timeout', 30)  # O(1)
register_config('retries', 3)   # O(1)

timeout = get_config('timeout')  # O(1)
```

## Performance Considerations

### Frequency of calls

```python
# globals() returns same dict object - O(1) each call
x = 42

for i in range(1000):
    d = globals()  # O(1) - returns same dict reference
    value = d['x']

# Caching is not necessary for globals(), but good for clarity
g = globals()  # O(1)
for i in range(1000):
    value = g['x']  # O(1) each
```

### Large Namespaces

```python
# globals() remains O(1) regardless of namespace size
# Iterating over the returned dict is O(n)
for i in range(10000):
    globals()[f'var_{i}'] = i  # O(1) each

# Still O(1): returns the same global dict object
g = globals()

# Iteration scales with number of entries - O(n)
names = [k for k in g if k.startswith("var_")]

# Prefer dict for custom data
my_data = {}
for i in range(10000):
    my_data[f'var_{i}'] = i  # O(1) each
```

## Version Notes

- **Python 3.13**: PEP 667: `locals()` in a function builds a fresh snapshot dict on every call, in O(m²) because each name is looked up in the frame. Earlier versions fill the frame's one dict in O(m) and return it, so two snapshots taken in the same call are the same object. `frame.f_locals` becomes a live proxy: O(1) to obtain, and writes through it reach the function's variables
- **All versions**: `globals()` is the frame's globals dict itself, and `locals()` at module or class scope is the namespace itself

## Related Functions

- **[vars()](vars.md)** - Similar to locals() but for objects
- **[dir()](dir.md)** - List names in namespace
- **[inspect.signature()](../stdlib/inspect.md)** - Get function signature
