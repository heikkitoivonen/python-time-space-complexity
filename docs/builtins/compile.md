# compile() Function Complexity

The `compile()` function compiles Python source code into a code object.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Parse code | O(n) | O(n) | n = source code length |
| Generate bytecode | O(n) | O(n) | Proportional to AST size |
| Total | O(n) | O(n) | Parsing + bytecode generation |

*Note: compile() is O(n) in the length of the source code. The resulting code object can be reused with eval()/exec() to avoid re-parsing.*

## Basic Usage

### Compiling Expressions

```python
# O(n) - compile to code object
code = compile("2 + 3", "<string>", "eval")
result = eval(code)  # 5

# Reuse compiled code (faster than re-parsing)
for i in range(1000):
    eval(code)  # No re-parsing
```

### Compiling Statements

```python
# O(n) - parse multiple statements
code = compile("""
x = 10
y = 20
z = x + y
""", "<string>", "exec")

namespace = {}
exec(code, namespace)
print(namespace['z'])  # 30
```

### Single Interactive Statement

```python
# O(n) - single statement mode
code = compile("x = 5", "<string>", "single")
exec(code)
# x is now 5 in current scope
```

## Complexity Details

### Parsing Overhead

```python
# O(n) - where n = code length
short_code = "x = 1"
compile(short_code, "<string>", "exec")  # O(5)

long_code = "x = " + "1 + 2 + 3 + ... + 100"
compile(long_code, "<string>", "exec")  # O(n)

# Deeply nested code - still O(n)
nested_code = "((((1))))"
compile(nested_code, "<string>", "exec")  # O(n)
```

### Modes

```python
# All O(n), but different requirements

# "eval" - single expression only
code = compile("x + 1", "<string>", "eval")

# "exec" - multiple statements
code = compile("x = 1\ny = 2", "<string>", "exec")

# "single" - single statement or expression (interactive)
code = compile("x = 1", "<string>", "single")
```

## Performance Patterns

### Reusing Compiled Code

```python
# Without compilation - O(n) per execution
for i in range(10000):
    eval("x ** 2")  # Parses each time - O(10000 * n)

# With compilation - O(n) once
code = compile("x ** 2", "<string>", "eval")
for i in range(10000):
    eval(code)  # O(n + 10000)

# Second approach is 10000x faster for repeated execution
```

### Pre-compilation Benefits

```python
import timeit

expr = "sum(range(100))"

# No pre-compilation
time1 = timeit.timeit(lambda: eval(expr), number=10000)

# Pre-compiled
code = compile(expr, "<string>", "eval")
time2 = timeit.timeit(lambda: eval(code), number=10000)

# time2 is significantly faster (no parsing)
```

## Code Objects

```python
# O(n) - produces code object
code_obj = compile("x + y", "<string>", "eval")

# Properties of code object
print(code_obj.co_names)       # Variable names: ('x', 'y')
print(code_obj.co_consts)      # Constants: (None,)
print(code_obj.co_code)        # Bytecode

# Reusable multiple times
result1 = eval(code_obj, {"x": 1, "y": 2})  # 3
result2 = eval(code_obj, {"x": 5, "y": 10})  # 15
```

## Compilation with Optimization

```python
# O(n) - optimize is active in Python 3
# optimize=-1 (inherit), 0 (no optimization), 1, or 2
code_default = compile("x = 1", "<string>", "exec", optimize=-1)
code_o1 = compile("assert x > 0", "<string>", "exec", optimize=1)
code_o2 = compile("def f():\n    'doc'\n    return 1", "<string>", "exec", optimize=2)
```

## Error Handling

```python
# O(n) - syntax checking happens during compilation
try:
    code = compile("x = ", "<string>", "exec")  # SyntaxError
except SyntaxError as e:
    print(f"Syntax error: {e}")

# vs runtime error (would happen during exec)
try:
    code = compile("undefined_function()", "<string>", "exec")
    # Compiles fine - error at runtime
except:
    pass
```

## Practical Examples

### Dynamic Function Generation

```python
# O(n) - compile and execute function definition
func_code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
"""

code = compile(func_code, "<string>", "exec")
namespace = {}
exec(code, namespace)

fib = namespace['fibonacci']
print(fib(10))  # 55
```

### Template Engine

```python
# O(n) - compile template
template = "Hello {{name}}, you have {{count}} messages"

# Simple substitution approach
code = compile(f'f"{template}"', "<string>", "eval")

data = {"name": "Alice", "count": 5}
# result = eval(code, data)  # Doesn't work directly with f-strings
# Use proper template engines like Jinja2 instead
```

### Configuration Script Execution

```python
# O(n) - load and execute configuration
config_script = """
DEBUG = True
DATABASE = "sqlite:///app.db"
SECRET_KEY = "my-secret"
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
"""

code = compile(config_script, "config.py", "exec")
config = {}
exec(code, config)

debug = config['DEBUG']
database = config['DATABASE']
```

## Bytecode Inspection

```python
import dis

# O(n) - compile and analyze
code = compile("x = 1 + 2", "<string>", "exec")

# View bytecode
dis.dis(code)
# Output shows:
#   1           0 LOAD_CONST               1 (3)
#               2 STORE_NAME               0 (x)
#               4 LOAD_CONST               0 (None)
#               6 RETURN_VALUE

# Helps understand Python's execution
```

## Filename Parameter

```python
# O(n) - filename helps with error messages
code = compile("invalid python", "script.py", "exec")
# SyntaxError will show: File "script.py", line 1

# Use meaningful filenames for debugging
```

## Comparison with eval()/exec()

```python
# eval(string) - compile + execute in one
eval("x + 1")  # O(n) - includes parsing

# exec(string) - compile + execute in one
exec("x = 1")  # O(n) - includes parsing

# Separate compilation - better for reuse
code = compile("x + 1", "<string>", "eval")
eval(code)  # O(m) - no parsing, just execution
```

## Security Considerations

```python
# compile() doesn't execute, just parses
# Still requires careful input handling

user_input = "__import__('os').system('rm -rf /')"
try:
    code = compile(user_input, "<string>", "eval")
    # Code object created successfully
    # Actual execution happens at eval(code)
except SyntaxError:
    pass

# Use ast.parse() for safer parsing without execution
import ast
try:
    tree = ast.parse(user_input)
    # Can inspect without executing
except SyntaxError:
    pass
```

## Edge Cases

### Empty Code

```python
# O(1) - minimal parsing
code = compile("", "<string>", "exec")
exec(code)  # Does nothing
```

### Comment-only Code

```python
# O(1) - ignored
code = compile("# This is a comment", "<string>", "exec")
exec(code)  # No operation
```

### Mixed Whitespace

```python
# O(n) - parses normally
code = compile("""

x = 1


y = 2

""", "<string>", "exec")
exec(code)
```

## Performance Considerations

### vs Source Execution

```python
import timeit

# Direct execution
t1 = timeit.timeit("eval('2 + 3')", number=10000)

# Compiled execution
t2 = timeit.timeit("eval(code)", setup="code = compile('2 + 3', '<string>', 'eval')", number=10000)

# t2 is much faster (no parsing)
```

### Memory Usage

```python
# Code objects are memory efficient
code = compile("x + y" * 1000, "<string>", "eval")
# Bytecode is more compact than original string
```

## Best Practices

✅ **Do**:

- Use `compile()` for code executed multiple times
- Save compiled code in variables for reuse
- Use meaningful filenames for debugging
- Pre-compile hot paths in performance-critical code

❌ **Avoid**:

- Compiling code that runs only once (overhead > benefit)
- Using `compile()` as security mechanism (it's not)
- Ignoring SyntaxErrors from user input
- Storing compiled code of untrusted source without review

## Related Functions

- **[eval()](eval.md)** - Evaluate expressions
- **[exec()](exec.md)** - Execute statements
- **[ast.parse()](https://docs.python.org/3/library/ast.html)** - Parse without compilation
- **[dis.dis()](https://docs.python.org/3/library/dis.html)** - Disassemble bytecode

## Version Notes

- **Python 2.x**: `compile()` accepts optional optimize flag
- **Python 3.x**: Optimize parameter deprecated (always optimized)
- **Python 3.8+**: Improved error messages
- **All versions**: Returns code object, requires eval()/exec() to execute
