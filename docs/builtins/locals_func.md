# locals() Function

The `locals()` function returns a dictionary containing the current local symbol table.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| `locals()` | O(n) | O(n) | n = local variables |
| Access variable | O(1) | O(1) | Direct dictionary access |

## Basic Usage

### Get Local Variables - Time: O(n)

```python
def example():
    x = 10
    y = 20
    z = x + y
    
    # Get all local variables - O(n)
    local_vars = locals()
    
    print(local_vars)
    # Output: {'x': 10, 'y': 20, 'z': 30}
    
    print(local_vars['x'])  # 10
    print(local_vars['y'])  # 20

example()
```

### Function Scope

```python
def outer():
    x = "outer"
    
    def inner():
        y = "inner"
        
        # locals() returns inner's variables - O(n)
        print(locals())  # {'y': 'inner'}
        
        # Note: x is not in locals(), it's in enclosing scope
        print(x)  # Can still access outer's x
    
    inner()
    
    # locals() returns outer's variables - O(n)
    print(locals())  # {'x': 'outer', 'inner': <function>}

outer()
```

### Module Level

```python
# At module level, locals() == globals()
x = 10
y = 20

# Get module-level locals - O(n)
local_vars = locals()
print('x' in local_vars)  # True
print('y' in local_vars)  # True
```

## Comparing locals() and globals()

### Scope Differences - Time: O(n)

```python
global_var = "global"

def example():
    local_var = "local"
    
    # locals() - current function scope - O(n)
    local_dict = locals()
    print(local_dict)
    # {'local_var': 'local'}
    
    # globals() - global scope - O(n)
    global_dict = globals()
    print('global_var' in global_dict)  # True
    print('local_var' in global_dict)   # False

example()
```

### Inspecting Variables

```python
def analyze():
    a = 1
    b = 2
    c = 3
    
    # Get local variables - O(n)
    local_vars = locals()
    
    # Iterate through locals - O(n)
    for name, value in local_vars.items():
        print(f"{name} = {value}")
    # Output:
    # a = 1
    # b = 2
    # c = 3

analyze()
```

## Practical Examples

### Dynamic Variable Access

```python
def get_var(var_name):
    """Get local variable by name."""
    x = 10
    y = 20
    z = 30
    
    # Get locals and access by name - O(n) to get, O(1) to access
    local_dict = locals()
    
    if var_name in local_dict:
        return local_dict[var_name]
    else:
        return None

print(get_var('x'))  # 10
print(get_var('unknown'))  # None
```

### Debugging/Inspection

```python
def debug_function(a, b, c):
    result = a + b + c
    multiplied = result * 2
    
    # Inspect all local variables - O(n)
    locals_dict = locals()
    
    print("=== Local Variables ===")
    for name, value in sorted(locals_dict.items()):
        print(f"  {name}: {value} ({type(value).__name__})")
    
    return multiplied

debug_function(1, 2, 3)
# Output:
# === Local Variables ===
#   a: 1 (int)
#   b: 2 (int)
#   c: 3 (int)
#   locals_dict: {...}
#   multiplied: 12 (int)
#   result: 6 (int)
```

### Variable Existence Check

```python
def check_variable(var_name):
    """Check if variable exists in current scope."""
    x = "exists"
    
    # Check using locals() - O(n) to get, O(1) for membership
    if var_name in locals():
        print(f"{var_name} exists with value: {locals()[var_name]}")
    else:
        print(f"{var_name} does not exist")

check_variable('x')  # x exists with value: exists
check_variable('y')  # y does not exist
```

## Comparison with globals()

```python
global_x = "global"

def func():
    local_x = "local"
    
    # locals() in function - O(n)
    local_dict = locals()
    
    # globals() in function - O(n)
    global_dict = globals()
    
    # Get specific values - O(1) each
    local_val = local_dict.get('local_x')    # "local"
    global_val = global_dict.get('global_x') # "global"
    
    return local_val, global_val

print(func())  # ('local', 'global')

# At module level, locals() == globals()
print(locals() == globals())  # True
```

## Important Notes

### Modifications

```python
def modify_attempt():
    x = 10
    
    # Get locals - O(n)
    local_dict = locals()
    
    # Modify the dictionary - O(1)
    local_dict['x'] = 20
    
    # Note: modifying locals() dict does NOT change x!
    print(x)  # Still 10, not 20
    
    # This is different in class body where locals() modifications ARE applied

modify_attempt()
```

### Class Definition

```python
# In class definition, locals() dict modifications ARE applied
class MyClass:
    x = 10
    local_dict = locals()  # Get locals - O(n)
    local_dict['y'] = 20   # Modify dictionary - O(1)
    
    print(x)  # 10
    print(y)  # 20 - THIS WORKS because we're defining the class
    # So y becomes a class attribute

print(MyClass.x)  # 10
print(MyClass.y)  # 20
```

## Performance Considerations

```python
def heavy_function(a, b, c, d, e, f, g, h):
    """Function with many local variables."""
    
    # Getting locals() is O(n) where n = number of locals
    # For 8 parameters, this is minimal overhead
    local_dict = locals()
    
    # Access is O(1)
    return local_dict.get('a', 0)

# Don't use locals() in tight loops for performance
# It creates a copy of the local symbol table each time

# ✅ Better for performance:
def fast_access(a, b, c):
    return a + b + c  # Direct access, no locals() call

# ❌ Slower:
def slow_access(a, b, c):
    return locals()['a'] + locals()['b'] + locals()['c']  # Creates dict 3 times!
```

## Best Practices

```python
# ✅ DO: Use locals() for debugging/introspection
def debug():
    x = 1
    y = 2
    print(locals())  # Good for understanding scope

# ✅ DO: Use it for variable existence checks
if 'var_name' in locals():
    process(locals()['var_name'])

# ✅ DO: Understand it's a snapshot
local_dict = locals()
x = 10
print('x' in local_dict)  # False - dict is a snapshot

# ❌ DON'T: Rely on modifications to locals()
locals()['x'] = 20
print(x)  # Still old value (except in class body)

# ❌ DON'T: Use in tight loops for performance
for i in range(1000000):
    v = locals()['var']  # Inefficient - creates dict each time

# ❌ DON'T: Serialize/pickle locals() dict
# It contains references that may not be picklable
```

## Related Functions

- [globals() Function](globals.md) - Get global symbol table
- [dir() Function](dir.md) - List accessible names
- [vars() Function](vars.md) - Get __dict__ of object
