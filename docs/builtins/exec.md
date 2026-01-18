# exec() Function Complexity

The `exec()` function executes Python code from a string.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Parse simple code | O(n) | O(n) | n = code length |
| Parse complex code | O(n) | O(n) | Includes all statements |
| Execute result | O(m) | O(m) | m = execution complexity |
| Total | O(n + m) | O(n + m) | Parse + execute |

## Basic Usage

### Simple Statements

```python
# O(n) - parse and execute
exec("x = 5")
# x is now 5 in current scope

exec("print('hello')")
# Output: hello

exec("for i in range(3): print(i)")
# Output: 0 1 2
```

### Assignments and Variables

```python
# O(n) - creates/modifies variables
code = """
result = 0
for i in range(10):
    result += i
"""
exec(code)
print(result)  # 45
```

### Function Definition

```python
# O(n) - defines function at runtime
code = """
def square(x):
    return x ** 2
"""
exec(code)
print(square(5))  # 25
```

## Complexity Details

### Code Parsing

```python
# O(n) - parsing is linear in code length
# Short code
exec("x = 1")  # O(1)

# Long code
code = "x = 1\n" * 100  # O(100)
exec(code)

# Complex code - still O(n)
complex_code = """
for i in range(10):
    for j in range(10):
        x = i + j
"""
exec(complex_code)  # O(n) - n = code length
```

### Execution Time

```python
# O(1) - quick assignment
exec("x = 5")

# O(n) - depends on actual operations
exec("x = sum(range(1000))")  # O(1000) - sum operation

# O(n²) - if code itself is O(n²)
exec("result = sum(range(1000)) for _ in range(1000))")  # O(n²)
```

### With Custom Scope

```python
# O(n + m) - parse code + scope overhead
# n = code length, m = scope size

# Small scope
scope = {"x": 10}
exec("y = x + 5", scope)  # O(n + 1)

# Large scope
big_scope = {f"var{i}": i for i in range(1000)}
exec("z = var0 + var1", big_scope)  # O(n + 1000)
```

## Performance Patterns

### Repeated Execution

```python
# O(n * k) - parses code k times
for i in range(1000):
    exec("x = x + 1")  # Re-parses each time

# Better - compile once
code = compile("x = x + 1", "<string>", "exec")
x = 0
for i in range(1000):
    exec(code)  # No re-parsing

# Even better - use Python directly
x = 0
for i in range(1000):
    x = x + 1  # Direct, no overhead
```

### Compiled vs Dynamic

```python
import time

# Dynamic execution
code = "y = x ** 2"
x = 0

start = time.time()
for _ in range(10000):
    x += 1
    exec(code)  # Parses each time
dynamic = time.time() - start

# Compiled execution
code = compile("y = x ** 2", "<string>", "exec")
x = 0

start = time.time()
for _ in range(10000):
    x += 1
    exec(code)  # No parsing
compiled = time.time() - start

# compiled is faster (no parsing overhead)
```

## Security Implications

### Why exec() is Dangerous

```python
# exec() executes arbitrary code
user_input = "import os; os.system('delete all files')"
# exec(user_input)  # DANGEROUS!

# Only use exec() with trusted code
# For untrusted code, there's no safe way
```

### Limited Sandboxing

```python
# Restricting builtins helps but doesn't fully protect
restricted = {"__builtins__": {}}
# exec("__import__('os').system('rm -rf /')", restricted)
# Still dangerous - can access other modules

# Proper security requires:
# - Never exec() untrusted code
# - Run in separate process with restricted permissions
# - Use specialized sandboxing tools
```

## Common Patterns

### Dynamic Class Creation

```python
# O(n) - creates class at runtime
code = """
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __str__(self):
        return f"Point({self.x}, {self.y})"
"""
namespace = {}
exec(code, namespace)
Point = namespace['Point']

p = Point(1, 2)
print(p)  # Point(1, 2)
```

### Configuration Execution

```python
# O(n) - execute config file (TRUSTED SOURCE ONLY)
config_code = """
DEBUG = True
LOG_LEVEL = "INFO"
DATABASE_URL = "sqlite:///data.db"
"""
config = {}
exec(config_code, config)

print(config['DEBUG'])  # True
```

### Dynamic Script Loading

```python
# O(n) - load and execute script
script_path = "user_script.py"
with open(script_path, 'r') as f:
    code = f.read()

# Only if you trust the script
exec(code)
```

## Comparison with alternatives

### exec() vs Regular Code

```python
# exec() - dynamic, slow
def dynamic_add(a, b):
    code = f"result = {a} + {b}"
    scope = {}
    exec(code, scope)
    return scope['result']

# Direct code - static, fast
def direct_add(a, b):
    return a + b

# direct_add is 100x+ faster for repeated calls
```

### exec() vs Lambdas

```python
# exec() for complex code - not ideal
code = "x = 0\nfor i in range(10): x += i"
exec(code)

# Better - use functions
def process():
    x = 0
    for i in range(10):
        x += i
    return x

result = process()
```

## Edge Cases

### Empty Code

```python
# O(1) - no-op
exec("")  # Nothing happens
```

### Modifying Outer Scope

```python
# exec() modifies provided scope, not outer scope by default
x = 10
code = "x = 20"

# Using default globals
exec(code)  # x is now 20 (modifies current namespace)

# Using custom scope
x = 10
scope = {}
exec(code, scope)  # x is still 10
print(scope['x'])  # 20
```

### Syntax Errors

```python
# O(n) - parsing fails immediately
try:
    exec("this is not valid python")
except SyntaxError as e:
    print(f"Syntax error: {e}")
```

### Import Side Effects

```python
# O(n) - imports have side effects
code = "import os; os.getcwd()"
exec(code)  # Module imported and loaded

# Repeated exec() may not re-import
exec(code)  # os already imported
```

## Performance Considerations

### Parsing Overhead

```python
import timeit

# Direct execution - fastest
timeit.timeit("x = 5")

# exec() with string - much slower
timeit.timeit("exec('x = 5')")

# Difference is string parsing overhead
```

### Memory Usage

```python
# exec() with large scope uses memory
big_scope = {f"var{i}": [0] * 1000 for i in range(1000)}
# Memory usage: 1000 * 1000 * 8 bytes ~= 8MB

exec("x = 1", big_scope)  # Must keep scope in memory
```

## Best Practices

✅ **Do**:

- Compile code once if executing multiple times
- Use `compile()` with exec for better performance
- Keep exec() code simple and clear
- Document where exec'd code comes from
- Only use with trusted code sources

❌ **Avoid**:

- Using `exec()` with user input (security risk)
- Executing complex code repeatedly without compilation
- Using `exec()` when regular functions would work
- Large exec'd code blocks (use modules instead)
- Assuming `exec()` is safe with restricted scope (it's not)
- Building code strings dynamically (hard to debug, test)

## Related Functions

- **[eval()](eval.md)** - Evaluate Python expressions
- **[compile()](compile.md)** - Compile code objects
- **[__import__()](index.md)** - Import modules dynamically

## Version Notes

- **Python 2.x**: `exec` is a statement, not a function
- **Python 3.x**: `exec()` is a function
- **All versions**: Security risk with untrusted input
