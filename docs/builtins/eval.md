# eval() Function Complexity

The `eval()` function evaluates a Python expression from a string.

## Complexity Analysis

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Parse simple expression | O(n) | O(n) | n = expression length |
| Parse complex expression | O(n) | O(n) | Includes nested calls |
| Evaluate result | O(m) | O(m) | m = result complexity |
| Total | O(n + m) | O(n + m) | Parse + evaluate |

## Basic Usage

### Simple Expressions

```python
# O(n) - parse and evaluate string expression
eval("2 + 3")              # 5
eval("len([1, 2, 3])")     # 3
eval("'hello'.upper()")    # 'HELLO'
eval("[1, 2, 3]")          # [1, 2, 3]
```

### With Variables

```python
# O(n) - parse + variable lookup
x = 10
eval("x + 5")  # 15

# With locals/globals
y = 20
eval("x + y", {"x": x, "y": y})  # 30
```

### Complex Expressions

```python
# O(n) - parsing is linear in expression length
expr = "2 * (3 + 4) ** 2 - 5 / 2"
result = eval(expr)  # Parsed and evaluated

# List comprehension
result = eval("[i**2 for i in range(10)]")
```

## Complexity Details

### Parsing Overhead

```python
# O(n) - string length dominates
# Short expression - fast parsing
eval("1+2")  # O(3)

# Long expression - slower parsing
expr = "1 + 2 + 3 + ... + 100"  # O(n)
result = eval(expr)

# Deeply nested - O(n) but more overhead
expr = "((((1))))"  # Still O(n), just more parsing steps
```

### Evaluation Overhead

```python
# O(1) - simple computation
eval("1 + 2")  # Quick

# O(n) - computation depends on operation
eval("[1, 2, 3, 4, 5]")  # O(n) - create list

# O(n log n) - expensive operations
eval("[*range(100)]")  # Creates list
```

### With Variable Lookup

```python
# O(n) - parse expression + O(1) lookup
x = 100
eval("x")  # O(1) - just lookup

# O(n) - parse + multiple lookups
eval("x + y + z")  # Still O(n) parsing

# Custom scope - O(n + m)
# n = expression length, m = scope size
scope = {f"var{i}": i for i in range(1000)}
eval("var0 + var1 + var2", scope)  # O(n + 1000)
```

## Security Considerations

### Why eval() is Dangerous

```python
# eval() executes arbitrary code
user_input = "import os; os.system('rm -rf /')"
# eval(user_input)  # DANGEROUS - would execute!

# Only use eval() with trusted input
# For untrusted input, use ast.literal_eval()
import ast
safe = ast.literal_eval("[1, 2, 3]")  # Safe - only literals
```

### Restricted Execution

```python
# eval() with custom globals/locals
restricted_scope = {"__builtins__": {}}
# eval("import os", restricted_scope)  # Still unsafe - can access builtins

# Use ast.literal_eval() for truly safe evaluation
import ast
result = ast.literal_eval("{'key': 'value'}")  # Safe
```

## Performance Patterns

### Repeated Evaluation

```python
# O(n * k) - parse expression k times
for i in range(1000):
    result = eval("x + 1")  # Re-parses each time

# Better - compile once, evaluate many times
code = compile("x + 1", "<string>", "eval")
for i in range(1000):
    x = i
    result = eval(code)  # O(k) - no re-parsing
```

### Compiled vs Dynamic

```python
# O(n) - parse each time
for x in range(1000):
    eval("x ** 2")  # Parses "x ** 2" each iteration

# O(1) - pre-compiled
code = compile("x ** 2", "<string>", "eval")
for x in range(1000):
    eval(code)  # No parsing, just evaluation
```

### Pre-compilation with compile()

```python
import time

expr = "sum(range(100))"

# Dynamic eval
start = time.time()
for _ in range(10000):
    eval(expr)
dynamic_time = time.time() - start

# Compiled eval
code = compile(expr, "<string>", "eval")
start = time.time()
for _ in range(10000):
    eval(code)
compiled_time = time.time() - start

# compiled_time is faster (no parsing overhead)
```

## Safer Alternatives

### ast.literal_eval()

```python
import ast

# O(n) - parse and verify it's a literal
# Safe - only allows literals (no code execution)
result = ast.literal_eval("[1, 2, 3]")
result = ast.literal_eval("{'a': 1, 'b': 2}")
result = ast.literal_eval("'string'")

# Will raise ValueError for code
try:
    ast.literal_eval("1 + 2")  # ValueError - not a literal
except ValueError:
    pass
```

### compile() + eval()

```python
# O(n) - compile once
code = compile("x ** 2 + y", "<string>", "eval")

# O(1) - fast evaluation
x, y = 10, 5
result = eval(code)  # 105

# Multiple evaluations with same code
for x in range(10):
    y = x * 2
    result = eval(code)  # Efficient
```

## Common Patterns

### Dynamic Math Evaluation

```python
# O(n) - parse and evaluate user expression
def calculate(expr, **kwargs):
    # WARNING: Only use with trusted input!
    return eval(expr, {"__builtins__": {}}, kwargs)

# Safe because no builtins available
result = calculate("x + y", x=10, y=20)  # 30
```

### Configuration Values

```python
import ast

# O(n) - parse config safely
config_str = '{"timeout": 30, "retries": 3, "items": [1, 2, 3]}'
config = ast.literal_eval(config_str)
# Safe - only allows data structures
```

### Lambda/Function Creation (Avoid!)

```python
# O(n) - can create functions at runtime
# Generally a bad idea - use proper functions instead
func = eval("lambda x: x ** 2")
result = func(5)  # 25

# Better - define function normally
def square(x):
    return x ** 2

result = square(5)
```

## Edge Cases

### Empty Expression

```python
# O(1) - minimal parsing
try:
    eval("")  # SyntaxError: unexpected EOF
except SyntaxError:
    pass
```

### Statement Execution (Won't Work)

```python
# eval() only handles expressions, not statements
try:
    eval("x = 5")  # SyntaxError - can't assign
except SyntaxError:
    pass

# Use exec() for statements
exec("x = 5")
```

### Scope Isolation

```python
# O(n) - with custom scope
x = "outer"

# eval() uses provided scope, not outer scope
result = eval("x", {"x": "inner"})  # "inner"

# Without explicit scope, uses current scope
y = 10
result = eval("y")  # Uses current y
```

## Performance Considerations

### vs Direct Execution

```python
import timeit

# Direct code - fastest
timeit.timeit("1 + 2")  # ~0.01 µs

# eval() - much slower
timeit.timeit("eval('1 + 2')", setup="e = eval")  # ~1 µs (100x slower)

# Difference is parsing overhead
```

### String Building Cost

```python
# O(n) - if you build expression string
for i in range(1000):
    expr = str(i) + " + 1"  # O(1) to build
    result = eval(expr)     # O(1) to parse

# Total O(n) - acceptable
```

## Best Practices

✅ **Do**:

- Compile expressions once if evaluated multiple times
- Use `ast.literal_eval()` for untrusted data
- Use `compile()` for better performance with repeated evals
- Restrict globals/locals when evaluating untrusted code
- Provide clear error messages

❌ **Avoid**:

- Using `eval()` with user input (security risk)
- Evaluating complex expressions repeatedly (compile first)
- Using `eval()` when regular functions would work
- Creating functions with `eval()` (use `def` or `lambda`)
- Assuming `eval()` is safe with restricted scope (it's not)

## Related Functions

- **[exec()](exec.md)** - Execute Python statements
- **[compile()](compile.md)** - Compile code objects
- **[ast.literal_eval()](https://docs.python.org/3/library/ast.html#ast.literal_eval)** - Safe literal evaluation

## Version Notes

- **Python 2.x**: `eval()` behavior similar but unicode handling differs
- **Python 3.x**: Consistent behavior, better Unicode support
- **All versions**: Security risk with untrusted input
