# globals() and locals() Functions Complexity

The `globals()` and `locals()` functions return dictionary representations of the current global and local namespaces, providing access to all defined variables in those scopes.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `globals()` | O(1) | O(1) | Returns reference to existing global dict |
| `locals()` | O(m) | O(m) | Creates snapshot copy; m = number of local vars |
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

# globals() includes built-ins and module vars
print('print' in globals())  # Usually True (if imported)
```

### Local Namespace

```python
# Access local namespace - O(m)
def my_func():
    a = 1
    b = 2
    
    local_vars = locals()  # O(m) - creates dict
    print(local_vars['a'])  # O(1)
    print(local_vars['b'])  # O(1)
    
    return local_vars

result = my_func()  # O(m)
```

## Common Patterns

### Inspecting Variables

```python
# List all global variables - O(n)
x = 10
y = 20
z = 30

all_vars = globals()  # O(n)

# Filter variables (not functions/modules) - O(n)
my_vars = {k: v for k, v in all_vars.items() 
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
    
    # Access local variables - O(m)
    caller_locals = frame.f_locals  # O(m)
    
    return caller_locals

def caller():
    x = 10
    y = 20
    
    caller_vars = get_caller_locals()  # O(m)
    print(caller_vars)  # {'x': 10, 'y': 20}

caller()
```

## Function Scope

### Module Level

```python
# At module level, locals() == globals() - O(n)
X = 100

print(locals() is globals())  # True at module level
print(locals()['X'])  # O(1)
```

### Inside Functions

```python
# Inside function, locals() is different - O(m)
global_x = 10

def func():
    local_y = 20
    
    # Different namespaces
    print('local_y' in locals())   # True - O(1)
    print('local_y' in globals())  # False - O(1)
    print('global_x' in locals())  # False - O(1)
    print('global_x' in globals()) # True - O(1)

func()
```

### Nested Functions

```python
# Nested functions can access enclosing scope
def outer():
    x = 10
    
    def inner():
        y = 20
        
        # locals() shows only inner's variables
        print(locals())  # {'y': 20}
        
        # Access outer's x through closure, not locals()
        print(x)  # 10 (from enclosing scope)
    
    inner()

outer()
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
    locals()['x'] = 10  # O(1) - sets in dict
    
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
    
    debug_state(locals())  # O(m)

example_func()
```

### Serialize Local Variables

```python
import json

def save_state():
    """Save local variables to JSON"""
    local_data = locals()  # O(m)
    
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
    
    state = save_state()  # O(m)
    return state

print(task())
```

### Configuration Registry

```python
# Use globals() as simple registry - O(n)
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
# Many variables = expensive globals() call - O(n)
# In interactive session with many variables
for i in range(10000):
    globals()[f'var_{i}'] = i  # O(1) each

# Now globals() is O(10000)
g = globals()  # Slower!

# Prefer dict for custom data
my_data = {}
for i in range(10000):
    my_data[f'var_{i}'] = i  # O(1) each
```

## Advanced Patterns

### Inspecting Function Parameters

```python
import inspect

def my_func(a, b, c=10):
    # Get function signature
    sig = inspect.signature(my_func)  # O(1)
    
    # Get local variables
    local_vars = locals()  # O(m)
    
    # Show what was passed
    params = {}
    for param_name in sig.parameters:  # O(k) params
        params[param_name] = local_vars.get(param_name)
    
    return params

result = my_func(1, 2, 3)  # O(m)
print(result)  # {'a': 1, 'b': 2, 'c': 3}
```

### Metaprogramming

```python
# Create class dynamically - O(k)
def create_class(name, attrs):
    """Create class using globals()"""
    class_dict = {}  # O(1)
    
    for attr_name, attr_value in attrs.items():
        class_dict[attr_name] = attr_value
    
    # Create class (simplified)
    return type(name, (), class_dict)

MyClass = create_class('MyClass', {'x': 10, 'y': 20})
obj = MyClass()
print(obj.x)  # 10
```

## Debugging with Frame Inspection

```python
import sys

def get_caller_info():
    """Get information about calling function"""
    frame = sys.exc_info()[2]  # O(1)
    if frame is None:
        frame = sys.gettrace().f_back  # O(1)
    
    # Access caller's locals - O(m)
    locals_dict = frame.f_locals
    
    return {
        'line': frame.f_lineno,
        'locals': locals_dict
    }

def example():
    x = 10
    y = 20
    # info = get_caller_info()  # O(m)
```

## Version Notes

- **Python 2.x**: Same behavior
- **Python 3.x**: Same behavior
- **All versions**: O(1) for globals() (returns reference), O(m) for locals() (creates copy)

## Related Functions

- **[vars()](vars.md)** - Similar to locals() but for objects
- **[dir()](dir.md)** - List names in namespace
- **[inspect.signature()](inspect.md)** - Get function signature

## Best Practices

✅ **Do**:
- Use `globals()` for metaprogramming when needed
- Cache globals() if calling multiple times
- Use inspect module for reflection
- Be explicit about variable scope

❌ **Avoid**:
- Relying on locals() to set variables in functions
- Calling globals() in loops (cache it)
- Modifying globals() at module level (confusing)
- Using globals()/locals() instead of proper parameters
- Assuming locals() state persists after function returns
